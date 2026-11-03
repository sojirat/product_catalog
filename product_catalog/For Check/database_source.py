"""Read SQL Server export views using the project's active template mapping."""
import os
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE_DIR.parent))

from product_catalog.translation import connect_database, load_database_config


def identifier(value):
    if not isinstance(value, str) or not value:
        raise ValueError('Empty database identifier')
    return '[' + value.replace(']', ']]') + ']'


def open_database(env_path):
    if not env_path.is_file():
        raise FileNotFoundError(env_path)
    config = load_database_config(env_path)
    return connect_database(config), config.schema


def read_database(validator, env_path):
    from validation_domain import SCHEMAS

    connection, schema = open_database(env_path)
    try:
        with connection.cursor() as cursor:
            mapping_table = os.getenv('TEMPLATE_MAPPING_TABLE', 'template_mapping').strip()
            cursor.execute(f'SELECT * FROM {identifier(schema)}.{identifier(mapping_table)}')
            mappings = [row for row in cursor.fetchall() if row.get('isActive', 1)]
            for table, (sheet, required, fields) in SCHEMAS.items():
                # PO and POP workbooks both contain a sheet named Product Offer Price.
                anchor = 'Characteristics for Price' if table in ('m', 'pt') else 'ProductOffer'
                workbook_names = {
                    row.get('EXCEL File') for row in mappings
                    if str(row.get('EXCEL SHEET NAME', '')).strip() == anchor
                    and row.get('EXCEL File')
                } if table in ('m', 'o', 'pt') else set()
                targets = {
                    row['DATABASE NAME'].strip() for row in mappings
                    if str(row.get('EXCEL SHEET NAME', '')).strip() == sheet
                    and not str(row.get('UNOIN') or '').strip()
                    and (not workbook_names or row.get('EXCEL File') in workbook_names)
                }
                if len(targets) != 1:
                    raise ValueError(f'{sheet}: expected one active mapping, found {len(targets)}')
                target = next(iter(targets))
                sources = [target] + sorted({
                    row['DATABASE NAME'].strip() for row in mappings
                    if str(row.get('UNOIN') or '').strip() == target
                    and row['DATABASE NAME'].strip() != target
                })
                for source in sources:
                    qualified = f'{identifier(schema)}.{identifier(source)}'
                    # No DDL or writes to the source database.
                    cursor.execute(f'SELECT * FROM {qualified}')
                    columns = [column[0] for column in cursor.description]
                    if any(columns.count(name) != 1 for name in required):
                        raise ValueError(f'{source}: missing or duplicate columns: {required}')
                    batch = []
                    count = 0
                    while True:
                        row = cursor.fetchone()
                        if row is None:
                            break
                        count += 1
                        values = [row[name] for name in required]
                        if any(value is not None and not isinstance(value, str) for value in values):
                            raise ValueError(f'{source}: row {count} contains non-text validation values')
                        batch.append((qualified, sheet, count, *('' if v is None else v for v in values)))
                        if len(batch) >= 10000:
                            validator._insert(table, batch)
                            batch = []
                    validator._insert(table, batch)
                    validator.inputs.append({'source': qualified, 'sheet': sheet, 'table': table,
                                             'records': count, 'row_numbering': 'query result ordinal, starting at 1'})
                validator.ready.add(table)
    finally:
        connection.close()


def check_connection(env_path):
    connection, _ = open_database(env_path)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1 AS connection_ok')
            if cursor.fetchone()['connection_ok'] != 1:
                raise RuntimeError('Database connection check failed')
        print('Database connection OK')
    finally:
        connection.close()
