"""Resolve failed Excel inputs through UAT_CPC's mapping and read exported CSV."""
import logging
import re
from pathlib import Path
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile
from openpyxl.utils.exceptions import InvalidFileException

from database_source import identifier, open_database

LOG = logging.getLogger('po_pop')
READ_ERRORS = (OSError, ValueError, KeyError, TypeError, EOFError, BadZipFile, ParseError,
               SyntaxError, OverflowError, InvalidFileException)


def find_csv(xlsx_path, sheet, env_path):
    connection, schema = open_database(env_path)
    try:
        with connection.cursor() as cursor:
            # Values are parameters; Excel names never become SQL syntax.
            cursor.execute(
                f'SELECT * FROM [UAT_CPC].{identifier(schema)}.[table_mapping] '
                'WHERE [EXCEL File] = ? AND [EXCEL SHEET NAME] = ?',
                (xlsx_path.name, sheet))
            mappings = cursor.fetchall()
            if not mappings:
                # Raw exports have timestamped names; map back to their configured
                # raw filename, then look up the required Excel-file/sheet pair.
                cursor.execute(
                    f'SELECT * FROM [UAT_CPC].{identifier(schema)}.[table_mapping] '
                    'WHERE [EXCEL SHEET NAME] = ? OR [Template File(Sheet Name)] = ?', (sheet,sheet))
                candidates = cursor.fetchall()
                matches = [r for r in candidates if raw_name(r, xlsx_path).lower() == xlsx_path.name.lower()]
                excel_keys = {(r['EXCEL File'],r.get('EXCEL SHEET NAME') or sheet) for r in matches}
                if len(excel_keys) != 1:
                    raise ValueError(f'No unique EXCEL File mapping for {xlsx_path.name} / {sheet}')
                cursor.execute(
                    f'SELECT * FROM [UAT_CPC].{identifier(schema)}.[table_mapping] '
                    'WHERE [EXCEL File] = ? AND [EXCEL SHEET NAME] = ?',
                    next(iter(excel_keys)))
                mappings = cursor.fetchall()
    finally:
        connection.close()
    csv_root = next((p.parent / 'csv' for p in xlsx_path.parents if p.name.lower() == 'xlsx'), None)
    if csv_root is None:
        raise ValueError(f'Cannot locate sibling csv folder for {xlsx_path}')
    raw_names = {raw_name(row,xlsx_path) for row in mappings}
    filenames = {Path(name).with_suffix('.csv').name for name in raw_names if name}
    matches = {p.resolve() for name in filenames for p in csv_root.rglob(name)}
    if len(matches) != 1:
        raise ValueError(f'Expected one mapped CSV for {xlsx_path.name} / {sheet}, found {len(matches)}')
    return next(iter(matches))


def raw_name(mapping, xlsx_path):
    name = str(mapping.get('Raw data Output File') or '').strip()
    stamp = re.search(r'\d{14}', xlsx_path.stem)
    if '<ddmmyyyyhhmiss>' in name:
        if stamp is None:
            stamp = next((re.fullmatch(r'\d{14}', p.name) for p in xlsx_path.parents
                          if re.fullmatch(r'\d{14}', p.name)), None)
        if stamp is None:
            raise ValueError(f'No export timestamp for {xlsx_path}')
        name = name.replace('<ddmmyyyyhhmiss>', stamp.group())
    name = re.sub(r'[<>:"/\\|?*]+', '_', name)
    if not name:
        return ''
    return str(Path(name).with_suffix('.xlsx'))


def read_with_fallback(validator, path, table, sheet, env_path, on_source=None):
    row_count = len(validator.rows[table])
    issue_count = len(validator.issues)
    input_count = len(validator.inputs)
    was_ready = table in validator.ready
    try:
        validator.read_xlsx(path, table, sheet_name=sheet)
        if table in validator.ready:
            return None
        raise ValueError(f'Incomplete XLSX sheet: {sheet}')
    except READ_ERRORS as error:
        # A workbook can fail after inserting earlier batches. Replace that
        # attempt as a whole, including diagnostics, rather than appending CSV.
        del validator.rows[table][row_count:]
        del validator.issues[issue_count:]
        del validator.inputs[input_count:]
        validator.ready.discard(table)
        if was_ready:
            validator.ready.add(table)
        LOG.warning('XLSX failed: %s / %s (%s); resolving mapped CSV', path, sheet, error)
        csv_path = find_csv(path, sheet, env_path)
        if on_source:
            on_source(csv_path)
        try:
            with csv_path.open(encoding='utf-8-sig', newline='') as stream:
                validator._csv(stream, str(csv_path), table=table)
        except Exception:
            del validator.rows[table][row_count:]
            del validator.inputs[input_count:]
            raise
        validator.ready.add(table)
        validator.inputs[-1]['fallback_from'] = str(path)
        validator.inputs[-1]['fallback_sheet'] = sheet
        return csv_path
