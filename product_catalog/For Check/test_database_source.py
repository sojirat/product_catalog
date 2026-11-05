import io
import json
import logging
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from database_source import read_database, open_database
from validate_po_pop import SCHEMAS, Validator, main
from test_validator import CONFIG


class Cursor:
    def __init__(self, nontext=False, missing_mapping=False):
        self.nontext = nontext
        self.missing_mapping = missing_mapping
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql):
        self.queries.append(sql)
        if 'template_mapping' in sql:
            self.rows = [dict(zip(('EXCEL SHEET NAME', 'DATABASE NAME', 'UNOIN'),
                                  (sheet, table, '')))
                         for table, (sheet, _, _) in SCHEMAS.items()
                         if table not in ('pt','pv') and not (self.missing_mapping and table == 'po')]
            self.rows.append({'DATABASE NAME': 'po_extra', 'UNOIN': 'po'})
            for row in self.rows:
                row['EXCEL File'] = 'POP.xlsx' if row['DATABASE NAME'] in ('m', 'c', 'ch', 'pt') else 'PO.xlsx'
        else:
            source = sql.rsplit('[', 1)[1].rstrip(']')
            table = 'po' if source == 'po_extra' else source
            columns = SCHEMAS[table][1] + (['priceType','price_value'] if table == 'm' else [])
            self.description = [(column,) for column in columns]
            self.rows = [{column: '001' for column in columns}]
            if self.nontext:
                self.rows[0][columns[0]] = 123

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class Connection:
    def __init__(self, cursor):
        self.reader = cursor
        self.closed = False

    def cursor(self):
        return self.reader

    def close(self):
        self.closed = True


class DatabaseTests(unittest.TestCase):
    def check_source(self, cursor, error=None):
        connection = Connection(cursor)
        validator = Validator(CONFIG)
        with patch('database_source.open_database', return_value=(connection, 'dbo')):
            if error:
                with self.assertRaisesRegex(ValueError, error):
                    read_database(validator, Path('unused.env'))
            else:
                read_database(validator, Path('unused.env'))
                self.assertEqual(validator.ready, set(SCHEMAS))
                self.assertEqual(len(validator.rows['po']), 2)
                self.assertEqual(validator.rows['po'][0]['po'], '001')
        self.assertTrue(connection.closed)
        self.assertTrue(all(sql.startswith('SELECT ') for sql in cursor.queries))

    def test_all_sources_and_union_are_read_without_writes(self):
        self.check_source(Cursor())

    def test_nontext_values_fail_instead_of_silent_conversion(self):
        self.check_source(Cursor(nontext=True), 'non-text')

    def test_missing_mapping_fails_instead_of_passing(self):
        self.check_source(Cursor(missing_mapping=True), 'expected one active mapping')

    def test_connection_reuses_project_env_loader_and_connector(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / '.env'
            env_path.write_text('# test config', encoding='utf-8')
            config = SimpleNamespace(schema='dbo')
            connection = Connection(Cursor())
            with patch('database_source.load_database_config', return_value=config) as loader, \
                 patch('database_source.connect_database', return_value=connection) as connector:
                self.assertEqual(open_database(env_path), (connection, 'dbo'))
            loader.assert_called_once_with(env_path)
            connector.assert_called_once_with(config)

    def test_database_cli_reads_project_env_and_exports_reports_without_local_db(self):
        connection = Connection(Cursor())
        with tempfile.TemporaryDirectory() as directory, \
             patch('database_source.find_product_master', return_value={'001':[{'COMMERCIAL_NAME':'001','SAP_DESCRIPTION':'001'}]}), \
             patch('database_source.open_database', return_value=(connection, 'dbo')) as opener, \
             patch.dict('sys.modules', {'sqlite3': None}), \
             patch('logging.FileHandler', return_value=logging.NullHandler()), \
             patch('logging.basicConfig'), redirect_stdout(io.StringIO()):
            exit_code = main(['--database', '--out', directory])
            opener.assert_called_once_with(Path(__file__).resolve().parent.parent / '.env')
            self.assertIn(exit_code, (1, 2))  # synthetic source intentionally has invalid data
            summary_path = next(Path(directory).glob('run_*/summary.json'))
            summary = json.loads(summary_path.read_text(encoding='utf-8'))
            self.assertEqual(summary['source_counts']['po'], 2)
            self.assertEqual(summary['report_verification'], 'All written cells reopened and matched; no sampling')
            self.assertTrue(list(summary_path.parent.glob('*.xlsx')))
            self.assertEqual({p.suffix for p in summary_path.parent.iterdir()}, {'.json', '.xlsx', '.txt'})
        self.assertTrue(connection.closed)
