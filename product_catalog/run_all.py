import argparse
import re
import time
from pathlib import Path

from product_catalog.export_template_mapping import BASE_DIR
from sql_runner import split_mysql_script
from translation import (
    IdTranslator,
    TranslationJob,
    connect_database,
    load_database_config,
    load_run_config,
    run_translation_job,
    table_exists,
    translate_po_id,
    translate_variant_id,
    translate_promotion_id,
)

PO_JOB = TranslationJob(
    name="Translate Product Offering PO_ID",
    table_name="tbl_product_offering",
    id_column="PO_ID",
    original_column="PO_ID_ORIGINAL",
    transform=translate_po_id,
)

VARIANT_JOB = TranslationJob(
    name="Translate Product Offering Variant variantId",
    table_name="tbl_product_offering_variant",
    id_column="variantId",
    original_column="VARIANT_ID_ORIGINAL",
    transform=translate_variant_id,
)

PROMOTION_JOB = TranslationJob(
    name="Translate Promotion PROMOTION_ID",
    table_name="tbl_promotion",
    id_column="PROMOTION_ID",
    original_column="PROMOTION_ID_ORIGINAL",
    transform=translate_promotion_id,
)


def main() -> None:
    args = parse_args()
    config = load_database_config(BASE_DIR / ".env")
    run_config = load_run_config(BASE_DIR / ".env")
    connection = connect_database(config)
    timings = []
    started_at = time.perf_counter()

    try:
        with connection.cursor() as cursor:
            configure_run_session(cursor)
            kill_stale_database_sessions(cursor, config.database)

            if args.command == "run-flow":
                batch_id = measure(
                    timings,
                    "reset_and_load_product_mst",
                    reset_and_load_product_mst,
                    cursor,
                    connection,
                    config.database,
                    run_config,
                )
                measure(
                    timings,
                    "generate_translate_flow",
                    run_generate_flow,
                    timings,
                    cursor,
                    connection,
                    config.database,
                    run_config,
                    batch_id,
                )
    finally:
        connection.close()
        print_timing_summary(timings, started_at)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        nargs="?",
        choices=["run-flow"],
        default="run-flow",
        help="run-flow = generate + translate",
    )
    return parser.parse_args()


def configure_run_session(cursor) -> None:
    cursor.execute("SET SESSION lock_wait_timeout = 5")
    cursor.execute("SET SESSION innodb_lock_wait_timeout = 5")


def kill_stale_database_sessions(cursor, database_name: str) -> None:
    cursor.execute("SELECT CONNECTION_ID() AS connection_id")
    current_connection_id = cursor.fetchone()["connection_id"]
    cursor.execute("SHOW FULL PROCESSLIST")
    sessions = cursor.fetchall()
    killed_sessions = []

    for session in sessions:
        session_id = session.get("Id")
        if session_id == current_connection_id:
            continue

        if session.get("db") != database_name:
            continue

        if session.get("Command") == "Daemon":
            continue

        cursor.execute(f"KILL {int(session_id)}")
        killed_sessions.append(session)

    if not killed_sessions:
        return

    print("\n=== KILL STALE DATABASE SESSIONS ===")
    for session in killed_sessions:
        info = (session.get("Info") or "").strip().replace("\n", " ")
        if len(info) > 160:
            info = info[:157] + "..."

        print(
            "Killed "
            f"id={session.get('Id')} "
            f"command={session.get('Command')} "
            f"time={session.get('Time')}s "
            f"state={session.get('State') or '-'} "
            f"info={info or '-'}"
        )


def reset_and_load_product_mst(cursor, connection, database_name: str, run_config) -> int | None:
    print("\n=== RESET DATABASE OBJECTS ===")
    cursor.execute("UPDATE sequence_registry SET last_sequence = 0")

    if table_exists(cursor, database_name, "PRODUCT_MST"):
        cursor.execute("UPDATE PRODUCT_MST SET isGenerate = 0")

    execute_statements(
        cursor,
        [
            "DROP TABLE IF EXISTS PRODUCT_MST",
            "DROP TABLE IF EXISTS tbl_product_offering",
            "DROP TABLE IF EXISTS tbl_product_offering_category",
            "DROP TABLE IF EXISTS tbl_product_offering_char_value",
            "DROP TABLE IF EXISTS tbl_product_offering_variant",
            "DROP TABLE IF EXISTS tbl_product_offering_variant_unpivot",
            "DROP TABLE IF EXISTS tbl_product_offering_price",
            "DROP TABLE IF EXISTS tbl_promotion",
            "DROP TABLE IF EXISTS tbl_campaign_master",
            "DROP TABLE IF EXISTS tbl_contract_master",
            "DROP TABLE IF EXISTS generate_all_log",
            "DROP TABLE IF EXISTS ingest_batch_detail",
            "DROP TABLE IF EXISTS ingest_batch",
            "DROP VIEW IF EXISTS v_master_meta_campaign_master",
            "DROP VIEW IF EXISTS v_master_meta_contract_master",
            "DROP VIEW IF EXISTS v_product_mst",
            "DROP VIEW IF EXISTS v_product_offering",
            "DROP VIEW IF EXISTS v_product_offering_category",
            "DROP VIEW IF EXISTS v_product_offering_category_all",
            "DROP VIEW IF EXISTS v_product_offering_channel",
            "DROP VIEW IF EXISTS v_product_offering_char_value",
            "DROP VIEW IF EXISTS v_product_offering_market_segment",
            "DROP VIEW IF EXISTS v_product_offering_meta_extension_material_info",
            "DROP VIEW IF EXISTS v_product_offering_place",
            "DROP VIEW IF EXISTS v_product_offering_price",
            "DROP VIEW IF EXISTS v_product_offering_price_tax",
            "DROP VIEW IF EXISTS v_product_offering_spec_characteristic",
            "DROP VIEW IF EXISTS v_product_offering_variant",
            "DROP VIEW IF EXISTS v_product_offering_variant_product_offering_price",
            "DROP VIEW IF EXISTS v_product_offering_with_product_offering_price",
            "DROP VIEW IF EXISTS v_promotion",
            "DROP VIEW IF EXISTS v_promotion_action",
            "DROP VIEW IF EXISTS v_promotion_master_extension",
            "DROP VIEW IF EXISTS v_promotion_meta_ext_value_allowed_airtime_installment",
            "DROP VIEW IF EXISTS v_promotion_meta_ext_value_contract_detail",
            "DROP VIEW IF EXISTS v_promotion_meta_ext_value_extra_document"
        ],
    )
    connection.commit()
    print("Reset completed")

    print("\n=== COPY STAGING TABLE ===")
    validate_source_table(cursor, database_name, run_config.source_product_table)
    cursor.execute("DROP TABLE IF EXISTS stg_product_mst")
    cursor.execute(
        f"CREATE TABLE stg_product_mst AS SELECT * FROM {run_config.source_product_table}"
    )
    connection.commit()
    print(f"Copied {run_config.source_product_table} to stg_product_mst")

    call_procedure(cursor, connection, "staging_and_batch_tables", ())
    install_load_product_mst_only(cursor, connection, run_config.sql_dir)
    result_rows = call_procedure(
        cursor,
        connection,
        "load_product_mst_only",
        (run_config.load_batch_name, run_config.load_created_by),
    )
    batch_id = find_result_value(result_rows, "batch_id")
    return batch_id if batch_id is not None else run_config.batch_id


def execute_statements(cursor, statements: list[str]) -> None:
    for statement in statements:
        cursor.execute(statement)


def validate_source_table(cursor, database_name: str, table_name: str) -> None:
    if not table_name.replace("_", "").isalnum():
        raise ValueError(f"Unsafe source table name: {table_name}")

    if not table_exists(cursor, database_name, table_name):
        raise ValueError(f"Source table does not exist: {table_name}")


def install_load_product_mst_only(cursor, connection, sql_dir: Path) -> None:
    if not sql_dir.exists():
        raise FileNotFoundError(
            f"SQL_DIR does not exist: {sql_dir}. "
            "Set SQL_DIR in product_catalog/.env to the folder containing 02_load_product_mst.sql."
        )

    source_path = sql_dir / "02_load_product_mst.sql"
    if not source_path.exists():
        raise FileNotFoundError(
            f"SQL file not found: {source_path}. "
            "Set SQL_DIR in product_catalog/.env to the folder containing 02_load_product_mst.sql."
        )

    print("\n=== INSTALL load_product_mst_only ===")
    script = source_path.read_text()
    script = script.replace(
        "DROP PROCEDURE IF EXISTS load_product_mst",
        "DROP PROCEDURE IF EXISTS load_product_mst_only",
    )
    script = script.replace(
        "CREATE PROCEDURE load_product_mst(",
        "CREATE PROCEDURE load_product_mst_only(",
    )
    script = re.sub(
        r"\n\s*-- ={64}\n\s*-- STEP 8: เรียก generate_all ถ้ามี downstream\n\s*-- ={64}\n\s*IF v_downstream > 0 THEN\n\s*CALL generate_all\(v_batch_id, v_actor\);\n\s*END IF;\n",
        "\n",
        script,
        count=1,
    )

    for statement in split_mysql_script(script):
        cursor.execute(statement)

    connection.commit()
    print("Installed load_product_mst_only without generate_all")


def run_generate_flow(
    timings: list[tuple[str, float]],
    cursor,
    connection,
    database_name: str,
    run_config,
    batch_id: int | None,
) -> None:
    translator = IdTranslator()
    actor = run_config.triggered_by

    measure(
        timings,
        "01_generate_product_offering",
        call_procedure,
        cursor,
        connection,
        "generate_product_offering",
        (batch_id, actor),
    )

    if not table_exists(cursor, database_name, "tbl_product_offering"):
        print(
            "\nStop: tbl_product_offering does not exist. "
            "generate_product_offering returned before creating output, likely because PRODUCT_MST has no rows with isGenerate = 0."
        )
        return

    measure(
        timings,
        "02_translate_po_id",
        timed_translation_job,
        cursor,
        connection,
        PO_JOB,
        translator,
        database_name,
    )
    measure(
        timings,
        "02b_update_product_offering_category_po_id",
        update_product_offering_category_po_id,
        cursor,
        connection,
        database_name,
    )

    measure(
        timings,
        "03_generate_product_offering_char_value",
        call_procedure,
        cursor,
        connection,
        "generate_product_offering_char_value",
        (batch_id, actor),
    )
    measure(
        timings,
        "04_generate_product_offering_variant_unpivot",
        call_procedure,
        cursor,
        connection,
        "generate_product_offering_variant_unpivot",
        (),
    )
    measure(
        timings,
        "05_generate_product_offering_variant",
        call_procedure,
        cursor,
        connection,
        "generate_product_offering_variant",
        (batch_id, actor),
    )
    measure(
        timings,
        "06_translate_variant_id",
        timed_translation_job,
        cursor,
        connection,
        VARIANT_JOB,
        translator,
        database_name,
    )
    measure(
        timings,
        "07_generate_product_offering_price",
        call_procedure,
        cursor,
        connection,
        "generate_product_offering_price",
        (batch_id, actor),
    )
    measure(
        timings,
        "08_generate_promotion",
        call_procedure,
        cursor,
        connection,
        "generate_promotion",
        (batch_id, actor, 0),
    )
    measure(
        timings,
        "09_translate_promotion_id",
        timed_translation_job,
        cursor,
        connection,
        PROMOTION_JOB,
        translator,
        database_name,
    )
    measure(
        timings,
        "10_generate_contract_master",
        call_procedure,
        cursor,
        connection,
        "generate_contract_master",
        (batch_id, actor, 0),
    )
    measure(
        timings,
        "11_generate_campaign_master",
        call_procedure,
        cursor,
        connection,
        "generate_campaign_master",
        (batch_id, actor, 0),
    )
    measure(
        timings,
        "12_generate_lov",
        call_procedure,
        cursor,
        connection,
        "generate_lov",
        (),
    )


def call_procedure(cursor, connection, procedure_name: str, args: tuple) -> list[dict]:
    placeholders = ", ".join(["%s"] * len(args))
    sql = f"CALL {procedure_name}({placeholders})" if args else f"CALL {procedure_name}()"

    print(f"\n=== CALL {procedure_name} ===")
    started_at = time.perf_counter()
    cursor.execute(sql, args)
    result_rows = print_result_sets(cursor)
    connection.commit()
    print(f"Procedure completed in {format_duration(time.perf_counter() - started_at)}")
    return result_rows


def timed_translation_job(cursor, connection, job, translator, database_name: str) -> None:
    started_at = time.perf_counter()
    run_translation_job(cursor, connection, job, translator, database_name)
    print(f"Translation completed in {format_duration(time.perf_counter() - started_at)}")


def update_product_offering_category_po_id(cursor, connection, database_name: str) -> None:
    print("\n=== UPDATE tbl_product_offering_category.PO_ID ===")

    if not table_exists(cursor, database_name, "tbl_product_offering_category"):
        print("Skip: table tbl_product_offering_category does not exist")
        return

    if not table_exists(cursor, database_name, "tbl_product_offering"):
        print("Skip: table tbl_product_offering does not exist")
        return

    cursor.execute(
        """
        UPDATE tbl_product_offering_category tpc
        JOIN tbl_product_offering tpo
            ON tpc.PO_ID = tpo.PO_ID_ORIGINAL
        SET tpc.PO_ID = tpo.PO_ID
        WHERE tpo.PO_ID_ORIGINAL REGEXP '[ก-๙]'
        """
    )
    connection.commit()
    print(f"Updated rows: {cursor.rowcount}")


def print_result_sets(cursor) -> list[dict]:
    result_rows = []

    while True:
        if cursor.description:
            rows = cursor.fetchall()
            if rows:
                print(f"Result rows: {len(rows)}")
                for row in rows:
                    print(row)
                result_rows.extend(rows)

        if not cursor.nextset():
            break

    return result_rows


def find_result_value(rows: list[dict], key: str):
    for row in rows:
        if key in row:
            return row[key]

    return None


def measure(timings: list[tuple[str, float]], name: str, func, *args, **kwargs):
    started_at = time.perf_counter()

    try:
        return func(*args, **kwargs)
    finally:
        elapsed = time.perf_counter() - started_at
        timings.append((name, elapsed))
        print(f"\n=== {name} finished in {format_duration(elapsed)} ===")


def print_timing_summary(timings: list[tuple[str, float]], started_at: float) -> None:
    total = time.perf_counter() - started_at

    print("\n=== TIMING SUMMARY ===")
    for name, elapsed in timings:
        print(f"{name}: {format_duration(elapsed)}")

    print(f"TOTAL: {format_duration(total)}")


def format_duration(seconds: float) -> str:
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(int(minutes), 60)

    if hours:
        return f"{hours}h {minutes}m {secs:.3f}s"

    if minutes:
        return f"{minutes}m {secs:.3f}s"

    return f"{secs:.3f}s"


if __name__ == "__main__":
    main()
