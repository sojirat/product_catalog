import argparse
import itertools
import re
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = Path(__file__).resolve().parent
for path in (str(PROJECT_ROOT), str(PACKAGE_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from product_catalog.export_template_mapping import BASE_DIR
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
                    cursor.execute("SELECT TOP 1 batch_id FROM dbo.ingest_batch ORDER BY batch_id DESC")
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
    cursor.execute("SET LOCK_TIMEOUT 5000; SET XACT_ABORT ON;")


def kill_stale_database_sessions(cursor, database_name: str) -> None:
    # Killing other sessions requires server-level privileges and is unsafe in a
    # shared SQL Server database.  SQL Server handles stale client sessions.
    return


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
        "load_product_mst", #load_product_mst_only
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
    # SQL Server procedures are deployed as T-SQL batches. Do not try to
    # transform the legacy MySQL source at runtime.
    print("Using deployed SQL Server procedure dbo.load_product_mst")


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
    placeholders = ", ".join(["?"] * len(args))
    sql = f"EXEC dbo.{procedure_name} {placeholders}" if args else f"EXEC dbo.{procedure_name}"

    print(f"\n=== CALL {procedure_name} ===", flush=True)
    started_at = time.perf_counter()
    try:
        cursor.execute(sql, args)
        result_rows = print_result_sets(cursor)
        connection.commit()
    finally:
        pass

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
        UPDATE tpc
        SET tpc.PO_ID = tpo.PO_ID
        FROM dbo.tbl_product_offering_category AS tpc
        JOIN dbo.tbl_product_offering AS tpo
            ON tpc.PO_ID = tpo.PO_ID_ORIGINAL
        WHERE tpo.PO_ID_ORIGINAL LIKE N'%[ก-๙]%'
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
