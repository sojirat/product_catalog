"""
Installs the stored procedures/functions from product_catalog/sql/ into MySQL.

Used by the `db-init` service in docker-compose.yml as a one-shot job that runs
after MySQL is healthy and before the `app` service starts. Reuses
sql_runner.split_mysql_script so DELIMITER-based procedure/function bodies are
split correctly (same logic run_all.py relies on for 02_load_product_mst.sql).

NOTE: This only installs what exists in product_catalog/sql/. run_all.py's
generate flow also calls generate_cdm_master, generate_ussd_master,
generate_extension_cpc, generate_promotion_map_extension, and
generate_extension_group_type, none of which ship in this repo — those (and the
legacy SOURCE_PRODUCT_TABLE data referenced by product_catalog/.env) must come
from your production database. See DOCKER.md.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = Path(__file__).resolve().parent
for path in (str(PROJECT_ROOT), str(PACKAGE_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from sql_files import SQL_INSTALL_FILES
from sql_runner import split_mysql_script
from translation import connect_database, load_database_config

SQL_DIR = PACKAGE_DIR / "sql"

# Files that are ad-hoc queries/usage notes, not objects to install.
SKIP_FILES = {"00_notes.sql"}
SKIP_PREFIXES = ("QUERY", "CALL ")


def main() -> None:
    config = load_database_config(PACKAGE_DIR / ".env")
    connection = connect_database(config)

    try:
        with connection.cursor() as cursor:
            for filename in build_install_order():
                install_file(cursor, connection, filename)
    finally:
        connection.close()

    print("\n=== SQL install complete ===")
    print(
        "NOTE: generate_cdm_master, generate_ussd_master, generate_extension_cpc, "
        "generate_promotion_map_extension, and generate_extension_group_type are "
        "NOT in product_catalog/sql/ — steps 12/13/15/16/18 of `make run` will fail "
        "until those procedures are added from your production database."
    )


def build_install_order() -> list[str]:
    """SQL_INSTALL_FILES first (known dependency order), then any remaining
    function/procedure files not already covered, functions before procedures
    (best effort — dependency order between the extras is not guaranteed)."""
    ordered = list(SQL_INSTALL_FILES)

    remaining = [
        p.name
        for p in sorted(SQL_DIR.glob("*.sql"))
        if p.name not in ordered
        and p.name not in SKIP_FILES
        and not p.name.startswith(SKIP_PREFIXES)
    ]
    remaining.sort(key=lambda name: (not name.startswith("CREATE FUNCTION"), name))

    return ordered + remaining


def install_file(cursor, connection, filename: str) -> None:
    path = SQL_DIR / filename
    if not path.exists():
        print(f"Skip (not found): {filename}")
        return

    print(f"\n=== Installing {filename} ===")
    statements = split_mysql_script(path.read_text(encoding="utf-8"))
    for statement in statements:
        cursor.execute(statement)
    connection.commit()
    print("OK")


if __name__ == "__main__":
    main()
