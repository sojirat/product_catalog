"""Rule 13 source rows, exact reference comparisons, and report evidence."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from openpyxl import Workbook, load_workbook

from database_source import find_product_master
from test_validator import CONFIG
from validate_po_pop import Validator, export_report
from validation_domain import SCHEMAS


class Rule13Tests(unittest.TestCase):
    def setUp(self):
        self.v = Validator(CONFIG)
        self.v.ready.add('t')
        self.master = {'COMMERCIAL_NAME':'Phone', 'SAP_DESCRIPTION':'Description'}
        self.lookup = Mock(return_value={'001':[self.master]})
        self.v.product_master_lookup = self.lookup

    def insert(self, code='001', commercial='Phone', eng='Description', tha='Description', pid='pop1'):
        self.v._insert('t', [('meta.xlsx','POP_metaExt_productInfo',6, pid, code, commercial, eng, tha)])

    def test_all_fields_match_and_code_is_queried_once(self):
        self.insert()
        self.insert(pid='pop2')
        self.v.rule13()
        self.lookup.assert_called_once_with(['001'])
        self.assertEqual(self.v.issues, [])
        self.assertEqual(self.v.coverage['13_checked_rows'], 2)

    def test_each_mismatch_has_actual_and_expected_in_report(self):
        self.insert(commercial='phone', eng='Description ', tha='Thai description')
        self.v.rule13()
        self.assertEqual([issue['name'] for issue in self.v.issues],
                         ['commercialName','sapDescriptionEng','sapDescriptionTha'])
        self.assertEqual([issue['val'] for issue in self.v.issues],
                         ['phone','Description ','Thai description'])
        self.assertTrue(all(issue['rn'] == 6 and issue['sku'] == '001' for issue in self.v.issues))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'error.xlsx'
            export_report(self.v, path, 'ERROR')
            wb = load_workbook(path, read_only=True)
            try:
                rows = list(wb['Rule 13 (Errors 3)'].values)
                self.assertEqual(rows[1][15], repr('Phone'))
                self.assertEqual(rows[2][16], 'PRODUCT_MST.SAP_DESCRIPTION')
                for report_row, label, actual, column, expected in zip(
                        rows[1:], ['commercialName','sapDescriptionEng','sapDescriptionTha'],
                        ['phone','Description ','Thai description'],
                        ['COMMERCIAL_NAME','SAP_DESCRIPTION','SAP_DESCRIPTION'],
                        ['Phone','Description','Description']):
                    self.assertEqual(report_row[4],
                                     f"matCode='001': Meta POP.{label} = {actual!r} ไม่ตรงกับ PRODUCT_MST.{column} = {expected!r}")
            finally:
                wb.close()

    def test_blank_commercial_name_falls_back_to_sap_description(self):
        for blank in [None, '']:
            with self.subTest(blank=blank):
                self.v.rows['t'].clear()
                self.v.issues.clear()
                self.master['COMMERCIAL_NAME'] = blank
                self.insert(commercial='Description')
                self.v.rule13()
                self.assertEqual(self.v.issues, [])
                self.v.rows['t'].clear()
                self.insert(commercial='Wrong name')
                self.v.rule13()
                self.assertEqual(len(self.v.issues), 1)
                issue = self.v.issues[0]
                self.assertEqual(issue['related'], 'PRODUCT_MST.SAP_DESCRIPTION')
                self.assertEqual(issue['expected'], repr('Description'))
                self.assertIn("Meta POP.commercialName = 'Wrong name'", issue['reason'])
                self.assertIn("PRODUCT_MST.SAP_DESCRIPTION = 'Description'", issue['reason'])

    def test_whitespace_commercial_name_does_not_fall_back(self):
        self.master['COMMERCIAL_NAME'] = ' '
        self.insert(commercial='Description')
        self.v.rule13()
        self.assertEqual(self.v.issues[0]['related'], 'PRODUCT_MST.COMMERCIAL_NAME')
        self.assertEqual(self.v.issues[0]['expected'], repr(' '))

    def test_missing_and_blank_master(self):
        for result, code, expected in [({'001':[]}, '001','PRODUCT_MASTER_MISSING'),
                                       ({},'','META_MAT_CODE_EMPTY')]:
            with self.subTest(expected=expected):
                self.v.rows['t'].clear()
                self.v.issues.clear()
                self.lookup.return_value = result
                self.insert(code=code)
                self.v.rule13()
                self.assertEqual(self.v.issues[0]['code'], expected)

    def test_database_failure_is_review_and_missing_input_is_incomplete(self):
        self.insert()
        self.lookup.side_effect = RuntimeError('offline')
        self.v.rule13()
        self.assertEqual(self.v.summary()['rules'][12]['status'], 'INCOMPLETE')
        self.assertEqual(self.v.issues[0]['severity'], 'REVIEW')
        self.v.issues.clear()
        self.v.ready.clear()
        self.v.rule13()
        self.assertEqual(self.v.issues[0]['code'], 'MISSING_INPUT')

    def test_excluded_pop_is_not_queried(self):
        self.insert()
        self.v.ex_pop.add('pop1')
        self.v.rule13()
        self.lookup.assert_not_called()
        self.assertEqual(self.v.issues, [])

    def test_excel_starts_at_row6_and_csv_starts_after_header(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'meta.xlsx'
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = 'POP_metaExt_productInfo'
            header = SCHEMAS['t'][1]
            sheet.append(header)
            for label in ['description','type','Text','Cardinality 1']:
                sheet.append([label] * len(header))
            sheet.append(['pop1','001','Phone','Description','Description'])
            workbook.save(path)
            self.v.ready.clear()
            self.v.read_xlsx(path,'t')
            self.assertIn('t',self.v.ready)
            self.assertEqual(len(self.v.rows['t']),1)
            self.assertEqual(self.v.rows['t'][0]['rn'],6)
            self.v.rule13()
            self.assertEqual(self.v.issues,[])
            self.v.rows['t'].clear()
            csv_path = Path(directory) / 'meta.csv'
            with csv_path.open('w',encoding='utf-8',newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(header)
                writer.writerow(['pop1','001','Phone','Description','Description'])
            with csv_path.open(encoding='utf-8',newline='') as stream:
                self.v._csv(stream,str(csv_path),table='t')
            self.assertEqual(self.v.rows['t'][0]['rn'],2)
            self.v.rule13()
            self.assertEqual(self.v.issues,[])

    def test_sql_parameters_dedup_and_cleanup(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.side_effect = [[self.master], []]
        with patch('database_source.open_database',return_value=(connection,'dbo')):
            result = find_product_master(Path('test.env'),['001','001',"002'"])
        self.assertEqual(result,{'001':[self.master],"002'":[]})
        self.assertEqual(cursor.execute.call_count,2)
        for call, code in zip(cursor.execute.call_args_list,['001',"002'"]):
            sql,parameters = call.args
            self.assertIn('[dbo].[PRODUCT_MST] WHERE [MAT_CODE] = ?',sql)
            self.assertTrue(sql.startswith('SELECT TOP (1)'))
            self.assertIn('ORDER BY COALESCE([system_updated_at], [system_created_at]) DESC, [system_created_at] DESC, [PRODUCT_ID] DESC',sql)
            self.assertEqual(parameters,(code,))
        connection.close.assert_called_once()

    def test_query_error_closes_connection_and_empty_codes_do_not_connect(self):
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value.execute.side_effect = RuntimeError('offline')
        with patch('database_source.open_database',return_value=(connection,'dbo')):
            with self.assertRaises(RuntimeError):
                find_product_master(Path('test.env'),['001'])
        connection.close.assert_called_once()
        with patch('database_source.open_database') as opener:
            self.assertEqual(find_product_master(Path('test.env'),[]),{})
        opener.assert_not_called()

    def test_cli_wires_master_lookup_and_exports_rule13(self):
        import io
        import json
        import logging
        from contextlib import redirect_stdout
        from test_database_source import Cursor, Connection
        from validate_po_pop import main

        connection = Connection(Cursor())
        with tempfile.TemporaryDirectory() as directory, \
             patch('database_source.open_database',return_value=(connection,'dbo')), \
             patch('database_source.find_product_master',return_value={'001':[self.master]}) as lookup, \
             patch('logging.FileHandler',return_value=logging.NullHandler()), \
             patch('logging.basicConfig'), redirect_stdout(io.StringIO()):
            main(['--database','--out',directory])
            lookup.assert_called_once_with(Path(__file__).resolve().parent.parent / '.env',['001'])
            summary_path = next(Path(directory).glob('run_*/summary.json'))
            summary = json.loads(summary_path.read_text(encoding='utf-8'))
            self.assertEqual(summary['rules'][12]['error_cases'],3)
            path = next(summary_path.parent.glob('*01-14_ErrorOnly*.xlsx'))
            workbook = load_workbook(path,read_only=True)
            try:
                self.assertIn('Rule 13 (Errors 3)',workbook.sheetnames)
            finally:
                workbook.close()


if __name__ == '__main__':
    unittest.main()
