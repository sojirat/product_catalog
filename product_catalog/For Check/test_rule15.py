import csv
import io
import json
import logging
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock, patch

from test_validator import CONFIG
from validation_rules import RuleValidator
from validate_po_pop import main
from validation_domain import SCHEMAS


class Rule15Tests(unittest.TestCase):
    def setUp(self):
        self.v = RuleValidator(CONFIG)
        self.v.ready.add('v')
        self.v.run_date = date(2026, 11, 11)
        self.product = dict(PRODUCT_ID=1, MAT_CODE='001', PRODUCT_TYPE='DEVICE', CATEGORY='PHONE', EXPIRE_DATE=None)
        self.price = dict(PRODUCT_ID=1, PRICE_ID='price1', PRICE_GROUP='EUP', EFFECTIVE_DATE='2026-11-11', EXPIRE_DATE='2026-11-11')
        self.v.mat_code_catalog_lookup = Mock(return_value={'products':[self.product], 'prices':[self.price]})

    def variant(self, vid='v1', sku='001', group='EUP', po='po1'):
        self.v._insert('v', [('variants.xlsx','Product_Variants',2,po,vid,'price_group-mh_mg00557',group,sku)])

    def check(self):
        self.v.rule15()
        return self.v.issues

    def test_missing_sku_is_error_and_single_variant_does_not_check_group(self):
        self.assertEqual(self.check()[0]['code'], 'MAT_CODE_VARIANT_MISSING')
        self.v.issues.clear()
        self.variant(group='OTHER')
        self.assertEqual(self.check(), [])

    def test_multiple_variants_require_each_active_price_group(self):
        self.variant(group='STAFF')
        self.variant(vid='v2', group='OTHER')
        self.assertEqual(self.check()[0]['code'], 'MAT_CODE_PRICE_GROUP_MISSING')
        self.v.issues.clear()
        self.variant(vid='v3')
        self.assertEqual(self.check(), [])
        self.v.mat_code_catalog_lookup.return_value['prices'].append(dict(self.price, PRICE_ID='p2', PRICE_GROUP='WEB'))
        self.assertEqual(self.check()[0]['val'], 'WEB')

    def test_service_samm_blank_category_expired_and_future_prices_are_excluded(self):
        for changes in ({'PRODUCT_TYPE':'SERVICE'}, {'CATEGORY':'SAMM'}, {'CATEGORY':''}, {'CATEGORY':None}, {'EXPIRE_DATE':'2026-11-10'}):
            with self.subTest(changes=changes):
                original = self.product.copy()
                self.product.update(changes)
                self.v.issues.clear()
                self.assertEqual(self.check(), [])
                self.product.clear()
                self.product.update(original)
        for changes in ({'EFFECTIVE_DATE':'2026-11-12'}, {'EXPIRE_DATE':'2026-11-10'}, {'PRICE_ID':''}):
            with self.subTest(changes=changes):
                original = self.price.copy()
                self.price.update(changes)
                self.v.issues.clear()
                self.assertEqual(self.check(), [])
                self.price.clear()
                self.price.update(original)

    def test_inclusive_dates_and_blank_expiry(self):
        for expiry in (None, '', '2026-11-11', datetime(2026,11,11,0,0)):
            self.product['EXPIRE_DATE'] = expiry
            self.price['EXPIRE_DATE'] = expiry
            self.v.issues.clear()
            self.assertEqual(self.check()[0]['code'], 'MAT_CODE_VARIANT_MISSING')

    def test_bad_date_and_database_failure_are_review(self):
        self.price['EFFECTIVE_DATE'] = 'bad'
        self.assertEqual(self.check()[0]['severity'], 'REVIEW')
        self.v.issues.clear()
        self.v.mat_code_catalog_lookup.side_effect = OSError('offline')
        self.assertEqual(self.check()[0]['code'], 'MAT_CODE_LOOKUP_UNAVAILABLE')

    def test_excluded_po_is_not_reported_as_missing(self):
        self.v.ex_po.add('excluded')
        self.variant(po='excluded')
        self.assertEqual(self.check(), [])

    def test_cli_csv_only_rule15_writes_verified_report_and_hashes(self):
        self.price.update(EFFECTIVE_DATE='2000-01-01', EXPIRE_DATE=None)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            data=root/'Database'
            data.mkdir()
            export=root/'round'/'csv'/'Product Offer'
            export.mkdir(parents=True)
            for path, columns, rows in [
                (data/'PRODUCT_MST_202611111058.csv',list(self.product),[list(self.product.values())]),
                (data/'PRICE_MST_202611111058.csv',list(self.price),[list(self.price.values())]),
                (export/'PO_Product_Variants_11112026105800.csv',SCHEMAS['v'][1],[])]:
                with path.open('w',encoding='utf-8',newline='') as stream:
                    writer=csv.writer(stream)
                    writer.writerow(columns)
                    writer.writerows(rows)
            with patch('database_source.connect_database') as connect, patch('logging.basicConfig'), \
                 patch('logging.FileHandler',return_value=logging.NullHandler()), redirect_stdout(io.StringIO()):
                code=main(['--input-dir',str(root/'round'),'--csv','--database-dir',str(data),'--rules','15','--out',str(root/'results')])
            self.assertEqual(code,1)
            connect.assert_not_called()
            summary=json.loads(next((root/'results').glob('check_*/summary.json')).read_text(encoding='utf-8'))
            self.assertEqual(summary['selected_rules'],[15])
            self.assertEqual(summary['rules'][0]['error_cases'],1)
            self.assertEqual(len(summary['input_sha256']),3)

    def test_catalog_sql_reads_both_tables_and_closes_connection(self):
        from unittest.mock import MagicMock
        from database_source import read_mat_code_catalog
        connection=MagicMock()
        cursor=connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.side_effect=[[self.product],[self.price]]
        with patch('database_source.open_database',return_value=(connection,'dbo')):
            catalog=read_mat_code_catalog(Path('unused.env'))
        self.assertEqual(catalog, {'products':[self.product],'prices':[self.price]})
        self.assertEqual(cursor.execute.call_count,2)
        self.assertIn('[CATEGORY]',cursor.execute.call_args_list[0].args[0])
        self.assertIn('[PRICE_ID]',cursor.execute.call_args_list[1].args[0])
        connection.close.assert_called_once()

    def test_malformed_pairs_do_not_silently_pass_multiple_variants(self):
        self.variant()
        self.variant(vid='v2')
        for row in self.v.rows['v']:
            row['cids'] = 'color,price_group'
        issues=self.check()
        self.assertTrue(any(issue['code']=='MAT_CODE_VARIANT_CHAR_INVALID' for issue in issues))
        self.assertTrue(any(issue['severity']=='REVIEW' for issue in issues))

    def test_exact_sku_and_product_id_join(self):
        self.variant(sku='1')
        self.assertEqual(self.check()[0]['code'],'MAT_CODE_VARIANT_MISSING')
        self.v.issues.clear()
        self.price['PRODUCT_ID']=2
        self.assertEqual(self.check(),[])
        self.assertEqual(self.v.coverage['15_eligible_product_rows'],0)

    def test_expiry_1900_is_unset_for_product_and_price(self):
        for value in ('1900-01-01', '1900-01-01 00:00:00.000', datetime(1900,1,1)):
            with self.subTest(value=value):
                self.v.issues.clear()
                self.product['EXPIRE_DATE']=value
                self.price['EXPIRE_DATE']=value
                self.assertEqual(self.check()[0]['code'],'MAT_CODE_VARIANT_MISSING')
                self.assertEqual(self.v.coverage['15_eligible_product_rows'],1)

    def test_effective_date_1900_still_means_effective_in_the_past(self):
        self.price['EFFECTIVE_DATE']='1900-01-01'
        self.assertEqual(self.check()[0]['code'],'MAT_CODE_VARIANT_MISSING')

    def test_connection_failure_uses_csv_catalog_without_network(self):
        from database_csv import source_mode
        from database_source import read_mat_code_catalog
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for table,row in [('PRODUCT_MST',self.product),('PRICE_MST',self.price)]:
                with (root/(table+'_202611111058.csv')).open('w',encoding='utf-8',newline='') as stream:
                    writer=csv.writer(stream)
                    writer.writerow(list(row))
                    writer.writerow([r'\N' if value is None else value for value in row.values()])
            (root/'.env').touch()
            with source_mode(directory=root), patch('database_source.load_database_config'), \
                 patch('database_source.connect_database',side_effect=OSError('offline')) as connect:
                catalog=read_mat_code_catalog(root/'.env')
            connect.assert_called_once()
            self.assertEqual(catalog['products'][0]['MAT_CODE'],'001')
            self.assertIsNone(catalog['products'][0]['EXPIRE_DATE'])
