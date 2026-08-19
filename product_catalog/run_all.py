import argparse
import itertools
import re
import sys
import threading
import pymysql
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = Path(__file__).resolve().parent
for path in (str(PROJECT_ROOT), str(PACKAGE_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

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

# Map procedures to one or more output tables that indicate completion.
# The watcher will probe these tables and, if they contain rows, assume the
# procedure already finished on the server and close the client connection
# to force the client to recover and continue.
PROC_OUTPUT_TABLES = {
    "generate_product_offering_variant": ["tbl_product_offering_variant"],
    "generate_product_offering": ["tbl_product_offering"],
    "generate_product_offering_variant_unpivot": ["tbl_product_offering_variant_unpivot"],
    "generate_product_offering_char_value": ["tbl_product_offering_char_value"],
}


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
                skip_to = args.skip_to or 0
                if skip_to > 0:
                    cursor.execute("SELECT batch_id FROM ingest_batch ORDER BY batch_id DESC LIMIT 1")
                    row = cursor.fetchone()
                    if row is None:
                        raise RuntimeError("--skip-to requires an existing ingest_batch row but the table is empty.")
                    batch_id = row["batch_id"]
                    print(f"\n=== SKIP reset_and_load_product_mst — resuming from step {skip_to:02d} with batch_id={batch_id} ===")
                else:
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
                    skip_to,
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
    parser.add_argument(
        "--skip-to",
        type=int,
        default=None,
        metavar="STEP",
        help="Skip reset/load and start from this step number (e.g. --skip-to=5). Uses batch_id from the latest ingest_batch.",
    )
    return parser.parse_args()


def configure_run_session(cursor) -> None:
    cursor.execute("SET SESSION lock_wait_timeout = 5")
    cursor.execute("SET SESSION innodb_lock_wait_timeout = 5")
    cursor.execute("SET NAMES utf8mb4 COLLATE utf8mb4_general_ci")
    cursor.execute("SET CHARACTER SET utf8mb4")
    cursor.execute("SET character_set_connection=utf8mb4")
    cursor.execute("SET collation_connection = 'utf8mb4_general_ci'")


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
            "DROP TABLE IF EXISTS tbl_cdm_master",
            "DROP TABLE IF EXISTS tbl_ussd_master",
            "DROP TABLE IF EXISTS tbl_installment_master",
            "DROP TABLE IF EXISTS tbl_trade_product_installment_group",
            "DROP TABLE IF EXISTS generate_all_log",
            "DROP TABLE IF EXISTS ingest_batch_detail",
            "DROP TABLE IF EXISTS ingest_batch",
            "DROP VIEW IF EXISTS v_master_meta_campaign_master",
            "DROP VIEW IF EXISTS v_master_meta_contract_master",
            "DROP VIEW IF EXISTS v_master_meta_cdm_master",
            "DROP VIEW IF EXISTS v_master_meta_ussd_master",
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
            "DROP VIEW IF EXISTS v_promotion_meta_ext_value_allowed_airtime_installment",
            "DROP VIEW IF EXISTS v_promotion_meta_ext_value_contract_detail",
            "DROP VIEW IF EXISTS v_promotion_meta_ext_value_extra_document",
            "DROP VIEW IF EXISTS v_promotion_meta_ext_value_cdm_detail",
            "DROP VIEW IF EXISTS v_promotion_meta_ext_value_compensation_detail"
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
    skip_to: int = 0,
) -> None:
    translator = IdTranslator()
    actor = run_config.triggered_by

    def step(num: int, name: str, func, *args):
        if num < skip_to:
            print(f"\n=== SKIP {name} (--skip-to={skip_to}) ===")
            return
        measure(timings, name, func, *args)

    step(1, "01_generate_product_offering", call_procedure, cursor, connection, "generate_product_offering", (batch_id, actor))

    if skip_to <= 1 and not table_exists(cursor, database_name, "tbl_product_offering"):
        print(
            "\nStop: tbl_product_offering does not exist. "
            "generate_product_offering returned before creating output, likely because PRODUCT_MST has no rows with isGenerate = 0."
        )
        return

    step(2, "02_translate_po_id", timed_translation_job, cursor, connection, PO_JOB, translator, database_name)
    step(3, "02b_update_product_offering_category_po_id", update_product_offering_category_po_id, cursor, connection, database_name)
    step(4, "04_generate_product_offering_variant_unpivot", call_procedure, cursor, connection, "generate_product_offering_variant_unpivot", ())
    step(5, "05_generate_product_offering_variant", call_procedure, cursor, connection, "generate_product_offering_variant", (batch_id, actor))
    step(6, "06_generate_product_offering_char_value", call_procedure, cursor, connection, "generate_product_offering_char_value", (batch_id, actor))
    step(7, "07_translate_variant_id", timed_translation_job, cursor, connection, VARIANT_JOB, translator, database_name)
    step(8, "08_generate_product_offering_price", call_procedure, cursor, connection, "generate_product_offering_price", (batch_id, actor))
    step(9, "09_generate_promotion", call_procedure, cursor, connection, "generate_promotion", (batch_id, actor, 0))
    step(10, "10_generate_contract_master", call_procedure, cursor, connection, "generate_contract_master", (batch_id, actor, 0))
    step(11, "11_generate_campaign_master", call_procedure, cursor, connection, "generate_campaign_master", (batch_id, actor, 0))
    step(12, "12_generate_cdm_master", call_procedure, cursor, connection, "generate_cdm_master", (batch_id, actor, 0))
    step(13, "13_generate_ussd_master", call_procedure, cursor, connection, "generate_ussd_master", (batch_id, actor, 0))
    step(14, "14_generate_promotion_info_master", call_procedure, cursor, connection, "generate_promotion_info_master", (batch_id, actor, 0))
    # step(15, "15_generate_installment_master", call_procedure, cursor, connection, "generate_installment_master", (batch_id, actor, 0))
    step(16, "16_generate_extension_cpc", call_procedure, cursor, connection, "generate_extension_cpc", ())
    step(17, "17_generate_promotion_map_extension", call_procedure, cursor, connection, "generate_promotion_map_extension", ())
    step(18, "18_generate_lov", call_procedure, cursor, connection, "generate_lov", ())
    step(19, "19_generate_extension_group_type", call_procedure, cursor, connection, "generate_extension_group_type", ())


def call_procedure(cursor, connection, procedure_name: str, args: tuple) -> list[dict]:
    placeholders = ", ".join(["%s"] * len(args))
    sql = f"CALL {procedure_name}({placeholders})" if args else f"CALL {procedure_name}()"

    print(f"\n=== CALL {procedure_name} ===", flush=True)
    started_at = time.perf_counter()

    done = threading.Event()

    # Watcher thread: if the server no longer shows this connection id
    # (procedure finished on server side) but the client is still blocked
    # reading, we can close the client connection to force an error and
    # recover. This uses a separate DB connection to poll processlist.
    def watcher(conn_id: int, proc_name: str | None = None, check_interval: float = 5.0, max_checks: int = 60):
        try:
            from translation import load_database_config, connect_database
            config = load_database_config(BASE_DIR / ".env")
            probe_conn = connect_database(config)
            try:
                with probe_conn.cursor() as probe_cur:
                    for _ in range(max_checks):
                        if done.is_set():
                            return
                        probe_cur.execute(
                            'SELECT ID, COMMAND, STATE, TIME, INFO FROM information_schema.PROCESSLIST WHERE ID = %s',
                            (conn_id,),
                        )
                        row = probe_cur.fetchone()
                        # If the server no longer lists this connection id, force-close
                        # the client connection so the blocked read is interrupted.
                        if row is None:
                            print(f"[watcher] server no longer lists connection {conn_id}; closing client connection")
                            try:
                                connection.close()
                            except Exception:
                                pass
                            return

                        # If the session exists but is not actively running a query
                        # (e.g., STATE is Sleep), check whether the procedure's
                        # expected output tables already exist and contain rows. If
                        # so, assume the server-side work finished and close the
                        # client connection to allow the client to recover.
                        state = (row.get("STATE") or "").lower()
                        if proc_name and (not state or state.startswith("sleep") or row.get("COMMAND") != "Query"):
                            out_tables = PROC_OUTPUT_TABLES.get(proc_name, ())
                            for tbl in out_tables:
                                try:
                                    probe_cur.execute(f"SELECT 1 FROM {tbl} LIMIT 1")
                                    exists = probe_cur.fetchone()
                                    if exists:
                                        print(f"[watcher] detected output table {tbl} for {proc_name}; closing client connection")
                                        try:
                                            connection.close()
                                        except Exception:
                                            pass
                                        return
                                except Exception:
                                    # Table may not exist yet; ignore and continue polling
                                    pass

                        time.sleep(check_interval)
            finally:
                probe_conn.close()
        except Exception as e:
            print('[watcher] error:', e)

    def spin():
        for frame in itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"):
            if done.is_set():
                break
            elapsed = time.perf_counter() - started_at
            sys.stderr.write(f"\r{frame} {format_duration(elapsed)} elapsed...")
            sys.stderr.flush()
            time.sleep(0.1)
        sys.stderr.write("\r" + " " * 30 + "\r")
        sys.stderr.flush()

    spinner = threading.Thread(target=spin, daemon=True)
    spinner.start()
    try:
        # Get server connection id for this client session so watcher can check it
        try:
            cursor.execute('SELECT CONNECTION_ID() AS connection_id')
            conn_row = cursor.fetchone()
            server_conn_id = conn_row.get('connection_id') if conn_row else None
            print(f"[call_procedure] server connection id: {server_conn_id}")
        except Exception:
            server_conn_id = None

        watcher_thread = None
        if server_conn_id is not None:
            watcher_thread = threading.Thread(target=watcher, args=(server_conn_id, procedure_name), daemon=True)
            watcher_thread.start()

        print(f"[call_procedure] start execute: {procedure_name} at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        try:
            cursor.execute(sql, args)
        except pymysql.err.OperationalError as e:
            print(f"[call_procedure] OperationalError during execute: {e}")
            raise

        # Stop the spinner as soon as the CALL returns so the UI
        # doesn't appear to be stuck while we process results.
        print(f"[call_procedure] execute returned for: {procedure_name} at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        done.set()
        spinner.join()

        result_rows = print_result_sets(cursor)
        connection.commit()
        if watcher_thread is not None:
            watcher_thread.join(timeout=0)
    finally:
        done.set()
        spinner.join()

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
    max_preview_rows = 10

    while True:
        if cursor.description:
            row_count = 0
            preview_rows = []

            while True:
                rows = cursor.fetchmany(1000)
                if not rows:
                    break

                row_count += len(rows)
                remaining_preview_slots = max_preview_rows - len(preview_rows)
                if remaining_preview_slots > 0:
                    preview_rows.extend(rows[:remaining_preview_slots])

            if row_count:
                print(f"Result rows: {row_count}")
                for row in preview_rows:
                    print(row)
                if row_count > max_preview_rows:
                    print(f"... skipped printing {row_count - max_preview_rows} more rows")
                result_rows.extend(preview_rows)

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
