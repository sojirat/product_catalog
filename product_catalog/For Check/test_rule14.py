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
        self.v.rows['v'][0].update(cids='mainModel,brand,company,color,capacity,productType,product_sub_type,matType,model,unit_name,priceGroup',
                                         vals='main,ABLEMEN,AWN,STARLIGHT,128,DEVICE,SMARTPHONE,NORM,model,piece,EUP')
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
        self.assertEqual(self.check()[0]['code'],'VARIANT_PRODUCT_MASTER_COUNT')

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
            path=next(summary_path.parent.glob('*01-14_ErrorOnly*.xlsx'))
            wb=load_workbook(path,read_only=True)
            try:
                self.assertTrue(any(name.startswith('Rule 14 (Errors') for name in wb.sheetnames))
            finally:
                wb.close()


if __name__=='__main__':unittest.main()
