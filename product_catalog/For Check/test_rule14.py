import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from openpyxl import Workbook, load_workbook
from test_validator import CONFIG
from validate_po_pop import Validator, export_report
from validation_domain import PRODUCT_CHAR_COLUMNS
from database_source import find_variant_masters


class Rule14Tests(unittest.TestCase):
    def setUp(self):
        self.v = Validator(CONFIG)
        self.v.ready.update(('v','l','pv','c'))
        self.insert('v','po1','v1','color-mh_mg00524,company-mh_mg00551,price_group-mh_mg00557','STARLIGHT,AWN,EUP','001')
        self.insert('l','v1','pop1')
        self.insert('pv','pop1','Onetime','100.00')
        self.insert('c','pop1','brand-id','brand','ABLEMEN')
        self.master = dict.fromkeys(PRODUCT_CHAR_COLUMNS)
        self.master.update(PRODUCT_ID='product1',COLOR='STARLIGHT',COMPANY='AWN',BRAND='ABLEMEN')
        self.reference = {'001':{'products':[self.master], 'prices':[{'PRICE_GROUP':'EUP','INC_VAT':Decimal('100')}]}}
        self.lookup = Mock(return_value=self.reference)
        self.v.variant_master_lookup = self.lookup

    def insert(self, table, *values):
        self.v._insert(table,[('fixture.xlsx',table,2,*values)])

    def check(self):
        self.v.rule14()
        return self.v.issues

    def test_pass_includes_variant_and_pop_chars_and_decimal_price(self):
        self.assertEqual(self.check(),[])
        self.lookup.assert_called_once_with(['001'])

    def test_aliases_for_all_mapped_columns(self):
        self.v.rows['v'][0].update(cids='mainModel,brand,company,color,storageCapacity,productType,product_sub_type,matType,model,unit_name,priceGroup,device_family',
                                         vals='main,ABLEMEN,AWN,STARLIGHT,128,DEVICE,SMARTPHONE,NORM,deviceFamily,piece,EUP,model')
        self.master.update(MAIN_MODEL='main',CAPACITY='128',PRODUCT_TYPE='DEVICE',PRODUCT_SUBTYPE='SMARTPHONE',MAT_TYPE='NORM',MODEL='model',UNIT_NAME='piece')
        self.assertEqual(self.check(),[])

    def test_mismatches_both_missing_directions_and_conflicting_values(self):
        self.master.update(COLOR='BLACK',MODEL='model',COMPANY=None)
        self.insert('c','pop1','brand2','brand','Other')
        issues = self.check()
        self.assertEqual({issue['name'] for issue in issues},{'COLOR','MODEL','COMPANY','BRAND'})
        self.assertTrue(all(issue['pid']=='pop1' and issue['vid']=='v1' for issue in issues))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'errors.xlsx'
            export_report(self.v,path,'ERROR',rows_per_sheet=2)
            wb=load_workbook(path,read_only=True)
            try:
                self.assertEqual(wb.sheetnames,['Rule 14 (Errors 2)','Rule 14 2 (Errors 2)'])
            finally:
                wb.close()

    def test_storage_capacity_aliases_and_old_capacity_is_not_used(self):
        self.master['CAPACITY']='128GB'
        for name in ['storage_capacity','storageCapacity','storage_capacity-mh_mg001']:
            with self.subTest(name=name):
                self.v.rows['c']=self.v.rows['c'][:1]
                self.v.issues.clear()
                self.insert('c','pop1','storage-id',name,'128GB')
                self.assertEqual(self.check(),[])
        self.v.rows['c']=self.v.rows['c'][:1]
        self.v.issues.clear()
        self.insert('c','pop1','capacity-id','capacity','128GB')
        self.assertEqual(self.check()[0]['name'],'CAPACITY')

    def test_model_resolves_reference_across_variant_and_pop(self):
        self.master['MODEL']='AIR11M3WF_128GB'
        variant=self.v.rows['v'][0]
        variant['cids']+=',model-mh_mg00556'
        variant['vals']+=',appleIpadAir11SeriesHandset'
        self.insert('c','pop1','model-value-id','apple_ipad_air11_series_handset','AIR11M3WF_128GB')
        self.assertEqual(self.check(),[])
        self.v.rows['c'][-1]['val']='OTHER'
        self.assertEqual(self.check()[0]['val'],repr(['OTHER']))
        self.assertIn('model -> appleIpadAir11SeriesHandset',self.v.issues[0]['reason'])
        self.assertIn('AIR11M3WF_128GB',self.v.issues[0]['reason'])

    def test_model_missing_target_and_ambiguous_reference_are_errors(self):
        self.master['MODEL']='family'
        self.insert('c','pop1','model-id','model','family')
        self.assertEqual(self.check()[0]['code'],'VARIANT_MASTER_CHAR_MISMATCH')
        self.assertEqual(self.v.issues[0]['val'],repr([]))
        self.assertIn('จึงต้องไม่มีค่า MODEL',self.v.issues[0]['reason'])
        self.v.issues.clear()
        self.insert('c','pop1','model2-id','model','otherFamily')
        self.assertEqual(self.check()[0]['code'],'VARIANT_MODEL_REFERENCE_INVALID')

    def test_missing_model_target_passes_only_when_database_model_is_empty(self):
        self.insert('c','pop1','model-id','model','appleIpadAir11SeriesHandset')
        for database_value in [None, '']:
            with self.subTest(database_value=database_value):
                self.master['MODEL']=database_value
                self.v.issues.clear()
                self.assertEqual(self.check(),[])
        self.master['MODEL']='AIR11M3WF_128GB'
        issue,=self.check()
        self.assertEqual(issue['name'],'MODEL')
        self.assertEqual(issue['expected'],repr('AIR11M3WF_128GB'))
        self.assertIn('appleIpadAir11SeriesHandset',issue['reason'])

    def test_empty_model_target_is_also_no_model(self):
        self.insert('c','pop1','model-id','model','appleIpadAir11SeriesHandset')
        self.insert('c','pop1','target-id','apple_ipad_air11_series_handset','')
        self.master['MODEL']=None
        self.assertEqual(self.check(),[])

    def test_model_reference_snake_case_matches_camel_case_target(self):
        self.master['MODEL']='AIR11M3WF_128GB'
        self.insert('c','pop1','model-id','model','apple_ipad_air11_series_handset')
        self.insert('c','pop1','model-value-id','appleIpadAir11SeriesHandset','AIR11M3WF_128GB')
        self.assertEqual(self.check(),[])

    def test_invalid_pairs_and_multiple_onetime(self):
        self.v.rows['v'][0]['vals']='STARLIGHT'
        self.assertEqual(self.check()[0]['code'],'VARIANT_CHAR_LIST_INVALID')
        self.v.issues.clear()
        self.v.rows['v'][0]['vals']='STARLIGHT,AWN,EUP'
        self.insert('pv','pop1','Onetime','200')
        self.assertEqual(self.check()[0]['code'],'VARIANT_ONETIME_COUNT')
        self.lookup.assert_not_called()

    def test_missing_link_pop_and_onetime(self):
        for mode, code in [('links','VARIANT_ONETIME_COUNT'),('pop','VARIANT_PRICE_POP_MISSING'),('onetime','VARIANT_ONETIME_COUNT')]:
            with self.subTest(mode=mode):
                self.setUp()
                if mode=='links':self.v.rows['l'].clear()
                elif mode=='pop':self.v.rows['pv'].clear()
                else:self.v.rows['pv'][0]['price_type']='Pre-Booking'
                self.assertEqual(self.check()[0]['code'],code)

    def test_product_master_must_be_unique_not_latest(self):
        self.reference['001']['products'].append(self.master.copy())
        self.reference['001']['prices_by_product'] = {'product1': self.reference['001']['prices']}
        self.assertEqual(self.check(), [])

    def test_all_matching_products_use_latest_effective_price_after_group_filter(self):
        self.reference['001']['products'].append(dict(self.master, PRODUCT_ID='product2'))
        self.reference['001']['prices_by_product'] = {
            'product1':[{'PRICE_GROUP':'EUP','INC_VAT':'999','EFFECTIVE_DATE':'2026-01-01'}],
            'product2':[{'PRICE_GROUP':'EUP','INC_VAT':'100','EFFECTIVE_DATE':'2026-11-09'},
                        {'PRICE_GROUP':'STAFF','INC_VAT':'1','EFFECTIVE_DATE':'2027-01-01'}]}
        self.assertEqual(self.check(), [])

    def test_latest_effective_price_is_selected_for_single_product(self):
        from datetime import datetime
        self.reference['001']['prices'] = [
            {'PRICE_GROUP':'EUP','INC_VAT':'999','EFFECTIVE_DATE':datetime(2026,1,1)},
            {'PRICE_GROUP':'EUP','INC_VAT':'100','EFFECTIVE_DATE':'2026-11-09 10:00:00'}]
        self.assertEqual(self.check(), [])

    def test_equal_latest_dates_and_invalid_dates_are_review(self):
        for date in ('2026-11-09', 'invalid'):
            self.v.issues.clear()
            self.reference['001']['prices'] = [
                {'PRICE_GROUP':'EUP','INC_VAT':'100','EFFECTIVE_DATE':date},
                {'PRICE_GROUP':'EUP','INC_VAT':'999','EFFECTIVE_DATE':date}]
            self.assertEqual(self.check()[0]['severity'], 'REVIEW')

    def test_duplicate_sku_selects_matching_company_and_its_prices(self):
        other = dict(self.master, PRODUCT_ID='other', COMPANY='Other', COLOR='BLACK')
        self.reference['001']['products'] = [other, self.master]
        self.reference['001']['prices'] = []
        self.reference['001']['prices_by_product'] = {
            'other':[{'PRICE_GROUP':'EUP','INC_VAT':'999'}],
            'product1':[{'PRICE_GROUP':'EUP','INC_VAT':'100'}]}
        self.assertEqual(self.check(), [])

    def test_duplicate_sku_company_requires_one_matching_row(self):
        self.reference['001']['products'] = [dict(self.master, COMPANY='Other'), dict(self.master, COMPANY='Else')]
        self.assertEqual(self.check()[0]['code'], 'VARIANT_PRODUCT_MASTER_COUNT')
        self.v.issues.clear()
        self.v.rows['v'][0]['vals'] = 'STARLIGHT,awn,EUP'
        self.reference['001']['products'][0]['COMPANY'] = 'AWN'
        self.assertEqual(self.check()[0]['code'], 'VARIANT_PRODUCT_MASTER_COUNT')

    def test_csv_multiple_products_keep_prices_per_product(self):
        import csv
        from database_csv import source_mode
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (root/'PRODUCT_MST.csv').open('w',encoding='utf-8',newline='') as stream:
                writer=csv.writer(stream)
                writer.writerow(['MAT_CODE','PRODUCT_ID',*PRODUCT_CHAR_COLUMNS])
                for product_id, company in [(1,'AWN'),(2,'Other')]:
                    writer.writerow(['001',product_id,*[company if c=='COMPANY' else r'\N' for c in PRODUCT_CHAR_COLUMNS]])
            (root/'PRICE_MST.csv').write_text('PRODUCT_ID,PRICE_GROUP,INC_VAT,EFFECTIVE_DATE\n1,EUP,100,2026-01-01\n2,EUP,999,2026-11-09\n',encoding='utf-8')
            with source_mode(directory=root,force_csv=True):
                result=find_variant_masters(root/'.env',['001'])
            self.assertEqual(result['001']['prices_by_product'][1][0]['INC_VAT'],'100')
            self.assertEqual(result['001']['prices_by_product'][2][0]['INC_VAT'],'999')

    def test_price_mismatch_missing_group_duplicate_and_invalid(self):
        for prices, code in [([], 'VARIANT_PRICE_MASTER_MISSING'),
                             ([{'PRICE_GROUP':'EUP','INC_VAT':'101'}], 'VARIANT_PRICE_MISMATCH'),
                             ([{'PRICE_GROUP':'EUP','INC_VAT':None}], 'VARIANT_PRICE_INVALID'),
                             ([{'PRICE_GROUP':'EUP','INC_VAT':100}]*2, 'VARIANT_PRICE_MASTER_MULTIPLE')]:
            with self.subTest(code=code):
                self.v.issues.clear()
                self.reference['001']['prices']=prices
                self.assertEqual(self.check()[0]['code'],code)

    def test_exclusions_and_database_failure(self):
        self.v.ex_po.add('po1')
        self.assertEqual(self.check(),[])
        self.lookup.assert_not_called()
        self.v.ex_po.clear()
        self.lookup.side_effect=RuntimeError('offline')
        self.assertEqual(self.check()[0]['severity'],'REVIEW')

    def test_sql_join_parameters_and_connection_cleanup(self):
        connection=MagicMock()
        cursor=connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.side_effect=[[self.master],self.reference['001']['prices']]
        with patch('database_source.open_database',return_value=(connection,'dbo')):
            result=find_variant_masters(Path('test.env'),['001','001'])
        self.assertEqual(result,self.reference)
        self.assertEqual(cursor.execute.call_count,2)
        query,parameters=cursor.execute.call_args.args
        self.assertIn('INNER JOIN [dbo].[PRODUCT_MST]',query)
        self.assertIn('p.[PRODUCT_ID] = m.[PRODUCT_ID]',query)
        self.assertEqual(parameters,('001','product1'))
        connection.close.assert_called_once()

    def test_numeric_excel_price_and_missing_product_or_price_group(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'prices.xlsx'
            workbook=Workbook()
            sheet=workbook.active
            sheet.title='Product Offer Price'
            sheet.append(['Product Offer Price ID','priceType','price_value'])
            sheet.append(['pop1','Onetime',100.0])
            workbook.save(path)
            self.v.rows['pv'].clear()
            self.v.ready.discard('pv')
            self.v.read_xlsx(path,'pv')
            self.assertEqual(self.check(),[])
        self.v.rows['v'][0]['cids']='color,company'
        self.v.rows['v'][0]['vals']='STARLIGHT,AWN'
        self.assertEqual(self.check()[0]['code'],'VARIANT_PRICE_GROUP_COUNT')
        self.v.issues.clear()
        self.reference['001']['products']=[]
        self.assertEqual(self.check()[0]['code'],'VARIANT_PRODUCT_MASTER_COUNT')

    def test_repeated_sku_queries_once_and_checks_each_variant(self):
        self.insert('v','po1','v2','color,company,price_group','STARLIGHT,AWN,EUP','001')
        self.insert('l','v2','pop1')
        self.assertEqual(self.check(),[])
        self.lookup.assert_called_once_with(['001'])
        self.assertEqual(self.v.coverage['14_checked_variants'],2)

    def test_cli_wires_lookup_and_exports_rule14(self):
        import io
        import json
        import logging
        from contextlib import redirect_stdout
        from test_database_source import Cursor, Connection
        from validate_po_pop import main

        class OnetimeCursor(Cursor):
            def execute(self,sql):
                super().execute(sql)
                if sql.endswith('[m]'):
                    self.rows[0]['priceType']='Onetime'
                    self.rows[0]['price_value']='100'

        connection=Connection(OnetimeCursor())
        with tempfile.TemporaryDirectory() as directory, \
             patch('database_source.open_database',return_value=(connection,'dbo')), \
             patch('database_source.find_product_master',return_value={'001':[{'COMMERCIAL_NAME':'001','SAP_DESCRIPTION':'001'}]}), \
             patch('database_source.find_variant_masters',return_value=self.reference) as lookup, \
             patch('logging.FileHandler',return_value=logging.NullHandler()), \
             patch('logging.basicConfig'), redirect_stdout(io.StringIO()):
            main(['--database','--out',directory])
            lookup.assert_called_once_with(Path(__file__).resolve().parent.parent / '.env',['001'])
            summary_path=next(Path(directory).glob('run_*/summary.json'))
            summary=json.loads(summary_path.read_text(encoding='utf-8'))
            self.assertEqual(summary['rules'][13]['status'],'FAIL')
            path=next(summary_path.parent.glob('*01-15_ErrorOnly*.xlsx'))
            wb=load_workbook(path,read_only=True)
            try:
                self.assertTrue(any(name.startswith('Rule 14 (Errors') for name in wb.sheetnames))
            finally:
                wb.close()


if __name__=='__main__':unittest.main()
