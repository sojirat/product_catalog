"""Rule 12 filtering, database lookup, and Excel evidence."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from openpyxl import load_workbook

from database_source import find_resource_spec_pairs
from test_validator import CONFIG
from validate_po_pop import Validator, export_report


class Rule12Tests(unittest.TestCase):
    def setUp(self):
        self.v = Validator(CONFIG)
        self.v.ready.add('cv')
        self.lookup = Mock(return_value=set())
        self.v.resource_spec_lookup = self.lookup

    def insert(self, po='po1', spec='sim-rs_mg001', value='YES'):
        self.v._insert('cv', [('PO.csv', 'Char_Value CSV', len(self.v.rows['cv'])+2,
                               po, 'cid', 'Name', value, spec, 'SIM', 'string', 'FALSE')])

    def test_duplicate_rows_query_pair_once_and_report_one_error(self):
        self.insert()
        self.insert()
        self.v.rule12()
        self.lookup.assert_called_once_with([('po1', 'sim-rs_mg001')])
        self.assertEqual(len(self.v.issues), 1)
        issue = self.v.issues[0]
        self.assertEqual(issue['code'], 'INVALID_RESOURCE_SPEC')
        self.assertEqual(issue['occurrences'], 2)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'errors.xlsx'
            export_report(self.v, path, 'ERROR')
            workbook = load_workbook(path, read_only=True)
            try:
                rows = list(workbook['Rule 12 (Errors 1)'].values)
                self.assertEqual(rows[1][8], 'po1')
                self.assertIn('sim-rs_mg001', rows[1][16])
            finally:
                workbook.close()

    def test_found_pair_passes(self):
        self.insert()
        self.lookup.return_value = {('po1', 'sim-rs_mg001')}
        self.v.rule12()
        self.assertEqual(self.v.issues, [])
        self.assertEqual(self.v.coverage['12_checked_pairs'], 1)

    def test_filters_blank_non_resource_and_excluded_rows(self):
        self.insert(value='')
        self.insert(spec='service-ps_mg001')
        self.insert(po='excluded')
        self.v.ex_po.add('excluded')
        self.v.rule12()
        self.lookup.assert_not_called()
        self.assertEqual(self.v.issues, [])

    def test_whitespace_is_not_trimmed_and_offers_are_separate(self):
        self.insert(value=' ')
        self.insert(po='po2')
        self.lookup.return_value = {('po2', 'sim-rs_mg001')}
        self.v.rule12()
        self.lookup.assert_called_once_with([('po1', 'sim-rs_mg001'), ('po2', 'sim-rs_mg001')])
        self.assertEqual([issue['po'] for issue in self.v.issues], ['po1'])

    def test_multiple_resource_specs_are_reported_before_lookup(self):
        self.insert()
        self.insert(spec='other-rs_mg002')
        self.v.rule12()
        self.lookup.assert_not_called()
        self.assertEqual(self.v.issues[0]['code'], 'MULTIPLE_RESOURCE_SPEC')

    def test_database_failure_is_incomplete_not_invalid_resource(self):
        self.insert()
        self.lookup.side_effect = RuntimeError('connection failed')
        self.v.rule12()
        summary = self.v.summary()['rules'][11]
        self.assertEqual(summary['status'], 'INCOMPLETE')
        self.assertEqual(summary['error_cases'], 0)
        self.assertEqual(self.v.coverage['12_checked_pairs'], 0)

    def test_missing_cv_is_incomplete(self):
        self.v.ready.clear()
        self.v.rule12()
        self.assertEqual(self.v.issues[0]['code'], 'MISSING_INPUT')
        self.lookup.assert_not_called()

    def test_sql_parameters_deduplication_and_connection_cleanup(self):
        cursor = Mock()
        cursor.fetchone.side_effect = [{'pair_exists': 1}, None]
        connection = Mock()
        connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        connection.cursor.return_value.__exit__ = Mock(return_value=False)
        pairs = [('po1', "sim-rs_mg'001"), ('po2', 'sim-rs_mg002')]
        with patch('database_source.open_database', return_value=(connection, 'dbo')):
            found = find_resource_spec_pairs(Path('test.env'), pairs + pairs)
        self.assertEqual(found, {pairs[0]})
        self.assertEqual(cursor.execute.call_count, 2)
        for call, pair in zip(cursor.execute.call_args_list, pairs):
            query, parameters = call.args
            self.assertTrue(query.startswith('SELECT TOP (1)'))
            self.assertIn('[dbo].[vw_catalog_offer_specification_characteristic]', query)
            self.assertIn('[offer_id] = ? AND [specification_id] = ?', query)
            self.assertEqual(parameters, pair)
            self.assertNotIn(pair[0], query)
        connection.close.assert_called_once()

    def test_empty_lookup_does_not_connect(self):
        with patch('database_source.open_database') as opener:
            self.assertEqual(find_resource_spec_pairs(Path('test.env'), []), set())
        opener.assert_not_called()

    def test_query_failure_closes_connection(self):
        connection = Mock()
        cursor = Mock()
        connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        connection.cursor.return_value.__exit__ = Mock(return_value=False)
        cursor.execute.side_effect = RuntimeError('query failed')
        with patch('database_source.open_database', return_value=(connection, 'dbo')):
            with self.assertRaises(RuntimeError):
                find_resource_spec_pairs(Path('test.env'), [('po1', 'sim-rs_mg001')])
        connection.close.assert_called_once()

    def test_cli_wires_lookup_and_reports_rule12(self):
        import io
        import json
        import logging
        from contextlib import redirect_stdout
        from test_database_source import Cursor, Connection
        from validate_po_pop import main

        class ResourceCursor(Cursor):
            def execute(self, sql):
                super().execute(sql)
                if sql.endswith('[cv]'):
                    self.rows[0]['Char Value.Product Spec ID'] = 'sim-rs_mg001'

        connection = Connection(ResourceCursor())
        with tempfile.TemporaryDirectory() as directory, \
             patch('database_source.open_database', return_value=(connection, 'dbo')), \
             patch('database_source.find_resource_spec_pairs', return_value=set()) as lookup, \
             patch('logging.FileHandler', return_value=logging.NullHandler()), \
             patch('logging.basicConfig'), redirect_stdout(io.StringIO()):
            main(['--database', '--out', directory])
            lookup.assert_called_once_with(Path(__file__).resolve().parent.parent / '.env',
                                           [('001', 'sim-rs_mg001')])
            summary_path = next(Path(directory).glob('run_*/summary.json'))
            summary = json.loads(summary_path.read_text(encoding='utf-8'))
            self.assertEqual(summary['rules'][11]['status'], 'FAIL')
            report_path = next(summary_path.parent.glob('*01-15_ErrorOnly*.xlsx'))
            workbook = load_workbook(report_path, read_only=True)
            try:
                self.assertIn('Rule 12 (Errors 1)', workbook.sheetnames)
            finally:
                workbook.close()


if __name__ == '__main__':
    unittest.main()
