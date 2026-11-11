import csv
import io
import json
import logging
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from database_source import find_product_master, find_resource_spec_pairs, find_variant_masters
from validate_po_pop import main
from validation_domain import SCHEMAS, PRODUCT_CHAR_COLUMNS


class DatabaseCsvTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, table, columns, rows):
        with (self.root / (table + '.csv')).open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(columns)
            writer.writerows(rows)

    def mode(self, **kwargs):
        from database_csv import source_mode
        return source_mode(directory=self.root, **kwargs)

    def test_forced_csv_queries_latest_product_exact_codes_and_nulls(self):
        self.write('PRODUCT_MST', ['MAT_CODE','COMMERCIAL_NAME','SAP_DESCRIPTION','system_updated_at','system_created_at','PRODUCT_ID'], [
            ['001','Old','old',r'\N','2026-01-01',2],
            ['001','New','',r'\N','2026-01-01',10],
            ['1','Other','other','2026-11-01','2026-01-01',11]])
        with self.mode(force_csv=True), patch('database_source.connect_database') as connect:
            result = find_product_master(self.root / '.env', ['001'])
        connect.assert_not_called()
        self.assertEqual(result, {'001':[{'COMMERCIAL_NAME':'New','SAP_DESCRIPTION':''}]})

    def test_connection_failure_falls_back_and_preserves_resource_pairs(self):
        self.write('vw_catalog_offer_specification_characteristic', ['offer_id','specification_id'], [['001','rs1']])
        with self.mode(), patch('database_source.connect_database', side_effect=OSError('offline')), \
             patch('database_source.load_database_config'):
            (self.root / '.env').touch()
            self.assertEqual(find_resource_spec_pairs(self.root / '.env', [('001','rs1'),('1','rs1')]), {('001','rs1')})

    def test_variant_master_join_keeps_duplicates_and_null(self):
        self.write('PRODUCT_MST', ['MAT_CODE','PRODUCT_ID', *PRODUCT_CHAR_COLUMNS], [
            ['001',7,*([r'\N']*len(PRODUCT_CHAR_COLUMNS))]])
        self.write('PRICE_MST', ['PRODUCT_ID','PRICE_GROUP','INC_VAT','EFFECTIVE_DATE'], [[7,'EUP','100.00','2026-01-01'],[7,'EUP','101','2026-11-09']])
        with self.mode(force_csv=True):
            result = find_variant_masters(self.root / '.env', ['001'])
        self.assertIsNone(result['001']['products'][0]['MODEL'])
        self.assertEqual(len(result['001']['prices']), 2)

    def test_missing_file_and_column_raise(self):
        with self.mode(force_csv=True), self.assertRaises(FileNotFoundError):
            find_resource_spec_pairs(self.root / '.env', [('po','rs')])
        self.write('vw_catalog_offer_specification_characteristic', ['offer_id'], [['po']])
        with self.mode(force_csv=True), self.assertRaises(Exception):
            find_resource_spec_pairs(self.root / '.env', [('po','rs')])

    def test_export_rule13_uses_csv_reference_without_database(self):
        export = self.root / 'export' / 'csv' / 'MetaExtension POP'
        export.mkdir(parents=True)
        with (export / 'POP_metaExt_productInfo_01012026000000.csv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(SCHEMAS['t'][1])
            writer.writerow(['pop1','001','Phone','Description','Description'])
        self.write('PRODUCT_MST', ['MAT_CODE','COMMERCIAL_NAME','SAP_DESCRIPTION','system_updated_at','system_created_at','PRODUCT_ID'],
                   [['001','Phone','Description',r'\N','2026-01-01',1]])
        with patch('database_source.connect_database') as connect, \
             patch('logging.FileHandler', return_value=logging.NullHandler()), patch('logging.basicConfig'), redirect_stdout(io.StringIO()):
            code = main(['--input-dir',str(self.root / 'export'),'--csv','--database-dir',str(self.root),
                         '--rules','13','--out',str(self.root / 'results')])
        self.assertEqual(code, 0)
        connect.assert_not_called()

    def test_check_connection_never_succeeds_via_csv(self):
        from database_source import check_connection
        with self.mode(force_csv=True), self.assertRaises(FileNotFoundError):
            check_connection(self.root / 'missing.env')

    def test_timestamped_files_choose_latest_time_not_modification_time(self):
        from database_csv import resolve_csv
        for name in ('PRODUCT_MST_202611091058', 'product_mst_20261109105900',
                     'PRODUCT_MST_202611091059', 'PRODUCT_MST_EXTRA_202611091200',
                     'PRODUCT_MST_202613091200'):
            self.write(name, ['MAT_CODE'], [])
        self.assertEqual(resolve_csv(self.root, 'PRODUCT_MST').name, 'product_mst_20261109105900.csv')

    def test_exact_filename_takes_priority_over_timestamp(self):
        from database_csv import resolve_csv
        self.write('PRODUCT_MST', ['MAT_CODE'], [])
        self.write('PRODUCT_MST_202611091058', ['MAT_CODE'], [])
        self.assertEqual(resolve_csv(self.root, 'PRODUCT_MST').name, 'PRODUCT_MST.csv')

    def test_timestamped_reference_is_queried_and_registered(self):
        from unittest.mock import Mock
        self.write('vw_catalog_offer_specification_characteristic_202611091058',
                   ['offer_id','specification_id'], [['001','rs1']])
        callback = Mock()
        with self.mode(force_csv=True) as source:
            source.on_source = callback
            self.assertEqual(find_resource_spec_pairs(self.root / '.env', [('001','rs1')]), {('001','rs1')})
        self.assertEqual(callback.call_args.args[0].name, 'vw_catalog_offer_specification_characteristic_202611091058.csv')

    def test_mapping_union_and_inactive_entries(self):
        from database_source import read_database
        from validate_po_pop import Validator
        from test_validator import CONFIG
        self.write('template_mapping', ['EXCEL SHEET NAME','DATABASE NAME','UNOIN','EXCEL File','isActive'], [
            ['ProductOffer','offers','','PO','1'],
            ['ProductOffer','ignored','','PO','0'],
            ['ProductOffer','extra','offers','PO','1']])
        self.write('offers', ['Product Id'], [['001']])
        self.write('extra', ['Product Id'], [['002']])
        validator = Validator(CONFIG)
        with self.mode(force_csv=True):
            read_database(validator, self.root / '.env', tables={'po'})
        self.assertEqual([row['po'] for row in validator.rows['po']], ['001','002'])

    def test_malformed_and_duplicate_headers_do_not_become_missing_data(self):
        for content in ('offer_id,offer_id\npo,rs\n', 'offer_id,specification_id\npo,rs,extra\n'):
            with self.subTest(content=content):
                (self.root / 'vw_catalog_offer_specification_characteristic.csv').write_text(content, encoding='utf-8')
                with self.mode(force_csv=True), self.assertRaises(ValueError):
                    find_resource_spec_pairs(self.root / '.env', [('po','rs')])

    def test_csv_cli_selected_and_all_rules_never_connect_and_record_hashes(self):
        mapping = []
        for table, (sheet, columns, _) in SCHEMAS.items():
            if table in ('pt','pv'):
                continue
            workbook = 'POP' if table in ('m','c','ch') else 'PO'
            mapping.append([sheet,table,'',workbook,'1'])
            self.write(table, columns + (['priceType','price_value'] if table == 'm' else []), [])
        self.write('template_mapping', ['EXCEL SHEET NAME','DATABASE NAME','UNOIN','EXCEL File','isActive'], mapping)
        self.write('PRODUCT_MST', ['PRODUCT_ID','MAT_CODE','PRODUCT_TYPE','CATEGORY','EXPIRE_DATE'], [])
        self.write('PRICE_MST', ['PRODUCT_ID','PRICE_ID','PRICE_GROUP','EFFECTIVE_DATE','EXPIRE_DATE'], [])
        for rules in (['--rules','10'], []):
            with self.subTest(rules=rules), patch('database_source.connect_database') as connect, \
                 patch('logging.FileHandler', return_value=logging.NullHandler()), patch('logging.basicConfig'), redirect_stdout(io.StringIO()):
                out = self.root / ('all' if not rules else 'selected')
                code = main(['--csv','--database-dir',str(self.root),'--out',str(out),*rules])
                self.assertEqual(code, 0)
                connect.assert_not_called()
                summary = json.loads(next(out.glob('run_*/summary.json')).read_text(encoding='utf-8'))
                self.assertTrue(summary['input_sha256'])
                self.assertEqual(summary['selected_rules'], [10] if rules else list(range(1,16)))


if __name__ == '__main__':
    unittest.main()
