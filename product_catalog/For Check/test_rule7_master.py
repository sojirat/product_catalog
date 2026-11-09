import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from openpyxl import load_workbook
import test_validator
from validation_domain import MAIN, TYPE
from validate_po_pop import export_report


class Rule7MasterTests(unittest.TestCase):
    def setUp(self):
        fixture = test_validator.Tests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        fixture.delete('c', 'cid', MAIN)
        fixture.delete('cv', 'cid', MAIN)
        fixture.ins('cv', ('po1', TYPE, 'productType', 'DEVICE'))
        self.v = fixture.v
        self.v.main_model_lookup = Mock(return_value={'001':[{'MAIN_MODEL':None}]})
        self.fixture = fixture

    def run_rule(self):
        self.v.indexes()
        self.v.rule7()

    def test_null_passes_and_separate_report_lists_variant(self):
        self.run_rule()
        self.assertFalse(self.v.issues)
        self.assertEqual(self.v.main_model_passes[0]['vid'], 'v1')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'pass.xlsx'
            export_report(self.v, path, 'PASS')
            book = load_workbook(path, read_only=True)
            rows = list(book['Rule 7'].values)
            self.assertIn('v1', rows[1])
            self.assertIn('001', rows[1])
            book.close()

    def test_empty_string_passes_like_null_and_is_reported(self):
        self.v.main_model_lookup.return_value = {'001':[{'MAIN_MODEL':''}]}
        self.run_rule()
        self.assertFalse(self.v.issues)
        self.assertEqual(self.v.main_model_passes[0]['vid'], 'v1')
        self.assertIn("MAIN_MODEL = ''", self.v.main_model_passes[0]['related'])

    def test_nonempty_main_model_is_error(self):
        for value in (' ', 'Model'):
            with self.subTest(value=value):
                self.v.issues.clear()
                self.v.main_model_lookup.return_value = {'001':[{'MAIN_MODEL':value}]}
                self.run_rule()
                self.assertEqual(self.v.issues[0]['code'], 'DEVICE_MAIN_MISSING')
                self.assertEqual(self.v.issues[0]['vid'], 'v1')

    def test_missing_mat_code_is_error_and_lookup_failure_is_review(self):
        self.v.main_model_lookup.return_value = {'001':[]}
        self.run_rule()
        self.assertEqual(self.v.issues[0]['severity'], 'ERROR')
        self.v.issues.clear()
        self.v.main_model_lookup.side_effect = OSError('offline')
        self.run_rule()
        self.assertEqual(self.v.issues[0]['severity'], 'REVIEW')

    def test_all_candidate_variants_are_checked_and_codes_deduplicated(self):
        self.fixture.ins('v', ('po1','v2','color','BLACK','001'))
        self.fixture.ins('l', ('v2','p1'))
        self.run_rule()
        self.v.main_model_lookup.assert_called_once_with(['001'])
        self.assertEqual({row['vid'] for row in self.v.main_model_passes}, {'v1','v2'})

    def test_pop_main_model_skips_database(self):
        self.fixture.ins('c', ('p1', MAIN, 'mainModel', 'X'))
        self.run_rule()
        self.v.main_model_lookup.assert_not_called()

    def test_multiple_products_are_review_and_blank_sku_is_error(self):
        self.v.main_model_lookup.return_value = {'001':[{'MAIN_MODEL':None},{'MAIN_MODEL':None}]}
        self.run_rule()
        self.assertEqual(self.v.issues[0]['severity'], 'REVIEW')
        self.v.issues.clear()
        self.fixture.update('v', 'vid', 'v1', sku='')
        self.v.main_model_lookup.reset_mock()
        self.run_rule()
        self.assertEqual(self.v.issues[0]['severity'], 'ERROR')
        self.v.main_model_lookup.assert_not_called()

    def test_timestamped_csv_lookup_null_and_missing_code(self):
        from database_csv import source_mode
        from database_source import find_main_models
        path = self.fixture.root / 'PRODUCT_MST_202611091058.csv'
        path.write_text('MAT_CODE,MAIN_MODEL\n001,\\N\n002,\n', encoding='utf-8')
        with source_mode(directory=self.fixture.root, force_csv=True):
            result = find_main_models(self.fixture.root / '.env', ['001','002','003'])
        self.assertEqual(result, {'001':[{'MAIN_MODEL':None}], '002':[{'MAIN_MODEL':''}], '003':[]})
