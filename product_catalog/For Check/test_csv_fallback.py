import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from csv_fallback import find_csv, read_with_fallback
from validate_po_pop import Validator
from test_validator import CONFIG


class FallbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name) / '30102026110649'
        self.xlsx = root / 'xlsx' / 'Product Offer' / 'ProductOffer_30102026110649.xlsx'
        self.xlsx.parent.mkdir(parents=True)
        self.csv = root / 'csv' / 'Product Offer' / self.xlsx.with_suffix('.csv').name
        self.csv.parent.mkdir(parents=True)
        self.csv.write_text('Product Id\n001\n002\n', encoding='utf-8')
        self.v = Validator(CONFIG)

    def test_corrupt_xlsx_reads_full_csv_and_drops_partial_rows_and_errors(self):
        def broken(*args, **kwargs):
            self.v._insert('po', [('bad.xlsx', 'ProductOffer', 2, 'partial')])
            self.v.input_error('po', 'broken')
            self.v.inputs.append({'source': 'partial'})
            raise ValueError('damaged XML')
        callback = Mock()
        with patch.object(self.v, 'read_xlsx', side_effect=broken), \
             patch('csv_fallback.find_csv', return_value=self.csv):
            actual = read_with_fallback(self.v, self.xlsx, 'po', 'ProductOffer', Path('.env'), callback)
        self.assertEqual(actual, self.csv)
        self.assertEqual([r['po'] for r in self.v.rows['po']], ['001', '002'])
        self.assertEqual(self.v.issues, [])
        self.assertEqual(self.v.ready, {'po'})
        self.assertEqual(self.v.inputs[0]['fallback_from'], str(self.xlsx))
        callback.assert_called_once_with(self.csv)

    def test_missing_sheet_uses_csv(self):
        with patch.object(self.v, 'read_xlsx'), patch('csv_fallback.find_csv', return_value=self.csv):
            read_with_fallback(self.v, self.xlsx, 'po', 'ProductOffer', Path('.env'))
        self.assertEqual(len(self.v.rows['po']), 2)

    def test_successful_xlsx_does_not_connect_database(self):
        with patch.object(self.v, 'read_xlsx', side_effect=lambda *a, **k:self.v.ready.add('po')), \
             patch('csv_fallback.find_csv') as resolver:
            self.assertIsNone(read_with_fallback(self.v,self.xlsx,'po','ProductOffer',Path('.env')))
        resolver.assert_not_called()

    def test_malformed_csv_does_not_leave_partial_rows(self):
        self.csv.write_text('Product Id\n001\nwrong,width\n', encoding='utf-8')
        with patch.object(self.v,'read_xlsx'), patch('csv_fallback.find_csv',return_value=self.csv):
            with self.assertRaises(ValueError):
                read_with_fallback(self.v,self.xlsx,'po','ProductOffer',Path('.env'))
        self.assertEqual(self.v.rows['po'], [])
        self.assertNotIn('po',self.v.ready)

    def test_mapping_uses_excel_file_and_sheet_parameters(self):
        cursor = Mock()
        cursor.fetchall.return_value = [{'Raw data Output File':'ProductOffer_<ddmmyyyyhhmiss>.csv'}]
        connection = Mock()
        connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        connection.cursor.return_value.__exit__ = Mock(return_value=False)
        with patch('csv_fallback.open_database',return_value=(connection,'dbo')):
            self.assertEqual(find_csv(self.xlsx,'ProductOffer',Path('.env')),self.csv.resolve())
        sql, params = cursor.execute.call_args.args
        self.assertIn('[UAT_CPC].[dbo].[table_mapping]',sql)
        self.assertIn('WHERE [EXCEL File] = ? AND [EXCEL SHEET NAME] = ?',sql)
        self.assertEqual(params,(self.xlsx.name,'ProductOffer'))
        connection.close.assert_called_once()

    def test_raw_export_resolves_excel_name_then_queries_both_columns(self):
        cursor = Mock()
        row={'EXCEL File':'PO.xlsx','EXCEL SHEET NAME':'Product_Offer','Raw data Output File':'ProductOffer_<ddmmyyyyhhmiss>.csv'}
        cursor.fetchall.side_effect=[[],[row],[row]]
        connection=Mock()
        connection.cursor.return_value.__enter__=Mock(return_value=cursor)
        connection.cursor.return_value.__exit__=Mock(return_value=False)
        with patch('csv_fallback.open_database',return_value=(connection,'dbo')):
            self.assertEqual(find_csv(self.xlsx,'ProductOffer',Path('.env')),self.csv.resolve())
        self.assertEqual(cursor.execute.call_args.args[1],('PO.xlsx','Product_Offer'))
