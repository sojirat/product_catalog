"""Read SQL Server export views using the project's active template mapping."""
import os
from decimal import Decimal
import sys
from pathlib import Path
from validation_progress import batch_progress
import logging

LOG = logging.getLogger('po_pop')

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


def read_database(validator, env_path, tables=None):
    from validation_domain import SCHEMAS
    tables = set(SCHEMAS) if tables is None else set(tables)

    connection, schema = open_database(env_path)
    try:
        with connection.cursor() as cursor:
            mapping_table = os.getenv('TEMPLATE_MAPPING_TABLE', 'template_mapping').strip()
            cursor.execute(f'SELECT * FROM {identifier(schema)}.{identifier(mapping_table)}')
            mappings = [row for row in cursor.fetchall() if row.get('isActive', 1)]
            for table, (sheet, required, fields) in SCHEMAS.items():
                if table not in tables:
                    continue
                LOG.info('Reading database source: %s [%s]', sheet, table)
                # PO and POP workbooks both contain a sheet named Product Offer Price.
                anchor = 'Characteristics for Price' if table in ('m', 'pt', 'pv') else 'ProductOffer'
                workbook_names = {
                    row.get('EXCEL File') for row in mappings
                    if str(row.get('EXCEL SHEET NAME', '')).strip() == anchor
                    and row.get('EXCEL File')
                } if table in ('m', 'o', 'pt', 'pv') else set()
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
                        if table == 'pv' and isinstance(values[2], (int, float, Decimal)):
                            values[2] = str(values[2])
                        if any(value is not None and not isinstance(value, str) for value in values):
                            raise ValueError(f'{source}: row {count} contains non-text validation values')
                        batch.append((qualified, sheet, count, *('' if v is None else v for v in values)))
                        if len(batch) >= 10000:
                            validator._insert(table, batch)
                            batch = []
                            LOG.info('Reading database %s: %s records', source, count)
                    validator._insert(table, batch)
                    validator.inputs.append({'source': qualified, 'sheet': sheet, 'table': table,
                                             'records': count, 'row_numbering': 'query result ordinal, starting at 1'})
                validator.ready.add(table)
                batch_progress('Database input tables', len(validator.ready), len(tables), interval=1)
    finally:
        connection.close()


def find_resource_spec_pairs(env_path, pairs):
    """Read existence once per distinct offer/spec pair, sharing one connection."""
    pairs = sorted(set(pairs))
    if not pairs:
        return set()
    connection, schema = open_database(env_path)
    try:
        found = set()
        with connection.cursor() as cursor:
            query = (f'SELECT TOP (1) 1 AS pair_exists FROM {identifier(schema)}.'
                     '[vw_catalog_offer_specification_characteristic] '
                     'WHERE [offer_id] = ? AND [specification_id] = ?')
            for number, pair in enumerate(pairs, 1):
                if number == 1: LOG.info('Rule 12: querying resource specifications (%s pairs)',len(pairs))
                cursor.execute(query, pair)
                if cursor.fetchone() is not None:
                    found.add(pair)
                batch_progress('Rule 12 database pairs',number,len(pairs))
        return found
    finally:
        connection.close()


def find_product_master(env_path, codes):
    """Fetch the latest reference row once per MAT_CODE using audit timestamps."""
    codes = sorted(set(codes))
    if not codes:
        return {}
    connection, schema = open_database(env_path)
    try:
        result = {}
        with connection.cursor() as cursor:
            query = (f'SELECT TOP (1) [COMMERCIAL_NAME], [SAP_DESCRIPTION] FROM {identifier(schema)}.[PRODUCT_MST] '
                     'WHERE [MAT_CODE] = ? '
                     'ORDER BY COALESCE([system_updated_at], [system_created_at]) DESC, '
                     '[system_created_at] DESC, [PRODUCT_ID] DESC')
            for number, code in enumerate(codes, 1):
                if number == 1: LOG.info('Rule 13: querying PRODUCT_MST (%s MAT_CODEs)',len(codes))
                cursor.execute(query, (code,))
                rows = cursor.fetchall()
                if any(row[column] is not None and not isinstance(row[column], str)
                       for row in rows for column in ('COMMERCIAL_NAME', 'SAP_DESCRIPTION')):
                    raise ValueError('PRODUCT_MST contains non-text reference names')
                result[code] = rows
                batch_progress('Rule 13 database MAT_CODEs',number,len(codes))
        return result
    finally:
        connection.close()


def find_variant_masters(env_path, codes):
    """Rule 14 requires a unique product row, unlike rule 13's latest-row policy."""
    from validation_domain import PRODUCT_CHAR_COLUMNS
    codes = sorted(set(codes))
    if not codes:
        return {}
    connection, schema = open_database(env_path)
    try:
        result = {}
        with connection.cursor() as cursor:
            columns = ', '.join(identifier(column) for column in ('PRODUCT_ID', *PRODUCT_CHAR_COLUMNS))
            for number, code in enumerate(codes, 1):
                if number == 1: LOG.info('Rule 14: querying PRODUCT_MST and PRICE_MST (%s SKUs)',len(codes))
                cursor.execute(f'SELECT {columns} FROM {identifier(schema)}.[PRODUCT_MST] WHERE [MAT_CODE] = ?', (code,))
                products = cursor.fetchall()
                prices = []
                if len(products) == 1:
                    cursor.execute(f'SELECT p.[PRICE_GROUP], p.[INC_VAT] FROM {identifier(schema)}.[PRICE_MST] p '
                                   f'INNER JOIN {identifier(schema)}.[PRODUCT_MST] m ON p.[PRODUCT_ID] = m.[PRODUCT_ID] '
                                   'WHERE m.[MAT_CODE] = ? AND m.[PRODUCT_ID] = ?', (code, products[0]['PRODUCT_ID']))
                    prices = cursor.fetchall()
                result[code] = {'products': products, 'prices': prices}
                batch_progress('Rule 14 database SKUs',number,len(codes))
        return result
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
