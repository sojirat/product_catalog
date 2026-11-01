import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook
from validate_po_pop import Validator, SCHEMAS, UNIT, MODEL, MAIN, TYPE, parse_pairs, export_report, config_read

CONFIG=dict(exclude_po_ids=[],exclude_pop_ids=[],missing_model='REVIEW',blank_model='REVIEW',duplicate_same_po_mapping='REVIEW',cross_level_different_value='REVIEW',same_or_blank_sku='REVIEW')


class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.v=Validator(CONFIG)
  self.v.ready.update(SCHEMAS)
  self.ins('po',('po1',));self.ins('m',('p1',));self.ins('o',('po1','p1'))
  self.ins('v',('po1','v1','color','BLACK','001'));self.ins('l',('v1','p1'));self.ins('t',('p1','001'))
  for cid,name,val in [(UNIT,'unit','piece'),(MODEL,'model','widget'),(MAIN,'mainModel','DeviceModel')]:
   self.ins('c',('p1',cid,name,val));self.ins('cv',('po1',cid,name,val))
  self.ins('cv',('po1','color','color','BLACK'))

 def tearDown(self):self.tmp.cleanup()

 def ins(self,t,values):
  if t == 'cv':values = (*values, '', '', 'string', '')
  rn=len(self.v.rows[t])+2
  self.v._insert(t,[('fixture.xlsx',SCHEMAS[t][0],rn,*values)])

 def update(self, table, field, value, **changes):
  for row in self.v.rows[table]:
   if row[field] == value:row.update(changes)

 def delete(self, table, field, value):
  self.v.rows[table] = [r for r in self.v.rows[table] if r[field] != value]

 def run_checks(self):self.v.run()
 def cases(self,code):return [i for i in self.v.issues if i['code']==code]

 def test_full_pass(self):
  self.run_checks();self.assertTrue(all(r['status']=='PASS' for r in self.v.summary()['rules']))
 def test_comma_alignment(self):
  self.assertEqual(parse_pairs('company,dummy,group','AWN,z12,EUP')[0],[('company','AWN'),('dummy','z12'),('group','EUP')])
  self.assertEqual(parse_pairs('a,b','x,')[1],'EMPTY_MEMBER')
  self.assertEqual(parse_pairs('a,b','x')[1],'LENGTH_MISMATCH')
  self.assertEqual(parse_pairs('model','PRO9.7"256GB')[0],[('model','PRO9.7"256GB')])
  self.assertEqual(parse_pairs('a,b','"x,y",z')[1],'AMBIGUOUS_QUOTES')
 def test_unused_is_error_and_deduplicated_with_evidence(self):
  self.ins('cv',('po1','color','color','BLUE'));self.ins('cv',('po1','color','color','BLUE'))
  self.run_checks();r=self.cases('UNUSED_CHARACTERISTIC');self.assertEqual(len(r),1);self.assertEqual(r[0]['severity'],'ERROR');self.assertEqual(r[0]['occurrences'],2)
  export_report(self.v,self.root/'errors.xlsx','ERROR');w=load_workbook(self.root/'errors.xlsx',read_only=True)
  self.assertEqual(len(list(w['Rule 9 Sources'].values)),3);w.close()
 def test_different_sku_does_not_exempt_unused(self):
  self.ins('v',('po1','v2','color','BLACK','002'));self.ins('l',('v2','p1'));self.ins('t',('p1','002'));self.ins('cv',('po1','color','color','BLUE'))
  self.run_checks();self.assertFalse(self.cases('SAME_OR_EMPTY_SKU'));self.assertEqual(len(self.cases('UNUSED_CHARACTERISTIC')),1)
 def test_cross_po_does_not_count_as_usage(self):
  self.ins('cv',('po2','color','color','BLACK'));self.run_checks();self.assertEqual(self.cases('UNUSED_CHARACTERISTIC')[0]['po'],'po2')
 def test_empty_cv_value_not_unused(self):
  self.ins('cv',('po1','unused','unused',''));self.run_checks();self.assertFalse(self.cases('UNUSED_CHARACTERISTIC'))
 def test_multiple_links_any_match_passes_rule2(self):
  self.ins('l',('v1','p2'));self.run_checks();self.assertFalse(self.cases('POP_MISMATCH'))
 def test_rule3_dangling_variant_even_when_other_matches(self):
  self.ins('l',('missing_variant','p1'));self.run_checks();self.assertEqual(len(self.cases('VARIANT_MISSING')),1)
 def test_rule3_duplicate_source_rows_count(self):
  self.ins('v',('po1','v1','color','BLACK','001'));self.run_checks();self.assertEqual(self.cases('SKU_MATCH_COUNT')[0]['val'],'2')
 def test_unit_blank(self):
  self.update('c', 'cid', UNIT, val='');self.run_checks();self.assertEqual(len(self.cases('UNIT_EMPTY')),1)
 def test_model_missing_is_review(self):
  self.delete('c', 'cid', MODEL);self.run_checks();self.assertEqual(self.cases('MODEL_MISSING')[0]['severity'],'REVIEW')
 def test_model_duplicates(self):
  self.ins('c',('p1',MODEL,'model','widget'));self.run_checks();self.assertEqual(len(self.cases('MODEL_MULTIPLE')),2);self.assertEqual(len(self.cases('DUPLICATE_CHAR_NAME')),2)
 def test_model_secondary_search(self):
  self.ins('c',('p1','a','widget','1'));self.ins('c',('p1','b','widget','2'));self.run_checks();self.assertEqual(len(self.cases('MODEL_CHAR_NAME_MULTIPLE')),2)
 def test_rule7_device_fallback(self):
  self.delete('c', 'cid', MAIN);self.ins('cv',('po1',TYPE,'productType','DEVICE'));self.run_checks();self.assertFalse(self.cases('DEVICE_MAIN_MISSING'))
 def test_rule7_device_main_missing(self):
  self.delete('c', 'cid', MAIN);self.update('cv', 'cid', MAIN, val='');self.ins('cv',('po1',TYPE,'productType','DEVICE'));self.run_checks();self.assertEqual(len(self.cases('DEVICE_MAIN_MISSING')),1)
 def test_rule8_same_record_required(self):
  self.update('cv', 'cid', UNIT, name='wrong');self.ins('cv',('po1',UNIT,'unit','other'));self.run_checks();self.assertEqual(len(self.cases('CV_EXACT_MISSING')),1)
 def test_duplicate_levels(self):
  self.ins('c',('p1','color','color','BLACK'));self.run_checks();self.assertEqual(len(self.cases('DUPLICATE_LEVELS')),1)
 def test_different_levels_review(self):
  self.ins('c',('p1','color','color','BLUE'));self.run_checks();self.assertEqual(self.cases('DIFFERENT_LEVEL_VALUES')[0]['severity'],'REVIEW')
 def test_exclude_exact_not_range(self):
  self.v.ex_pop.add('p1');self.ins('m',('p2',));self.run_checks();self.assertEqual([r['pid'] for r in self.cases('MISSING_META')],['p2'])
 def test_bad_parse_blocks_unused_false_positive(self):
  self.update('v', 'vid', 'v1', vals='BLACK,BLUE');self.run_checks();self.assertTrue(self.cases('LENGTH_MISMATCH'));self.assertFalse(self.cases('UNUSED_CHARACTERISTIC'));self.assertTrue(self.cases('UNUSED_UNCERTAIN'))
 def test_case_and_whitespace_are_not_normalized(self):
  self.update('v', 'vid', 'v1', vals='black ');self.run_checks();self.assertEqual(len(self.cases('VARIANT_PAIR_NOT_ALLOWED')),1)
 def test_csv_newline_width_and_records(self):
  text=io.StringIO(newline='');w=csv.writer(text);w.writerow(SCHEMAS['cv'][1]);w.writerow(['po1','x','name','a\nb','','','string','']);text.seek(0)
  self.assertEqual(self.v._csv(text,'embedded.csv'),1);r=next(r for r in self.v.rows['cv'] if r['cid']=='x');self.assertEqual(r['rn'],2);self.assertEqual(r['val'],'a\nb')
  with self.assertRaises(ValueError):self.v._csv(io.StringIO(','.join(SCHEMAS['cv'][1])+'\na,b\n'),'bad.csv')
 def test_excel_formula_not_executed_in_report(self):
  self.v.add('9.4','ERROR','TEST','literal',val='=1+1');export_report(self.v,self.root/'r.xlsx','ERROR');w=load_workbook(self.root/'r.xlsx',read_only=True);c=list(w['Rule 9 (Errors 1)'].rows)[1][14];self.assertEqual(c.value,'=1+1');self.assertEqual(c.data_type,'s');w.close()
 def test_reports_separate_rules_and_preserve_severity_filter(self):
  for rule,severity in [('2','ERROR'),('9.1','ERROR'),('9.4','ERROR'),('6','REVIEW'),('7','WARNING')]:
   self.v.add(rule,severity,'TEST','fixture')
  for severity,expected in [('ERROR',{'2':['2'],'9':['9.1','9.4']}),('REVIEW',{'6':['6'],'7':['7']})]:
   path=self.root/(severity+'.xlsx');counts=export_report(self.v,path,severity)
   with self.subTest(severity=severity):
    workbook=load_workbook(path)
    try:
     def sheet_name(number):
      count=len(expected.get(str(number),[]))
      return 'Rule '+str(number)+(' PASS' if not count else f' (Errors {count})' if severity=='ERROR' else '')
     self.assertEqual(workbook.sheetnames,[sheet_name(n) for n in range(1,11)]+(['All','Char duplicate detail'] if severity=='ERROR' else []))
     for number in range(1,11):
      has_issues=str(number) in expected
      sheet=workbook[sheet_name(number)]
      self.assertEqual(sheet.sheet_properties.tabColor.rgb,'FFFF0000' if has_issues else 'FF00B050')
      rules=[row[1] for row in list(sheet.values)[1:]]
      self.assertEqual(rules,expected.get(str(number),[]))
      self.assertEqual(counts[sheet.title],len(rules)+1)
    finally:workbook.close()
 def test_error_sheet_count_includes_continuation_rows_without_header(self):
  self.v.add('7','ERROR','TEST','long evidence',related='x'*60001)
  path=self.root/'continued.xlsx';counts=export_report(self.v,path,'ERROR')
  workbook=load_workbook(path)
  try:
   sheet=workbook['Rule 7 (Errors 3)']
   self.assertEqual(sheet.max_row,4)
   self.assertEqual(counts[sheet.title],4)
   self.assertEqual(sheet.sheet_properties.tabColor.rgb,'FFFF0000')
  finally:workbook.close()
 def test_input_issues_have_their_own_report_sheet(self):
  self.v.input_error('po','missing column',src='fixture.xlsx')
  path=self.root/'input.xlsx';export_report(self.v,path,'REVIEW')
  workbook=load_workbook(path,read_only=True)
  try:
   self.assertEqual(list(workbook['Input Issues'].values)[1][1],'INPUT')
   self.assertEqual(len(workbook.sheetnames),11)
  finally:workbook.close()
 def test_xlsx_hidden_rows_and_split_sheets(self):
  w=Workbook();s=w.active;s.title='ProductOffer';s.append(['Product Id']);s.append(['p1']);s.row_dimensions[2].hidden=True
  s=w.create_sheet('ProductOffer (2)');s.append(['Product Id']);s.append(['p2']);p=self.root/'p.xlsx';w.save(p)
  self.v.rows['po'].clear();self.v.ready.remove('po');self.v.read_xlsx(p,'po');self.assertIn('po',self.v.ready);self.assertEqual(len(self.v.rows['po']),2)
 def test_nontext_id_blocks_rule(self):
  w=Workbook();s=w.active;s.title='ProductOffer';s.append(['Product Id']);s.append([123]);p=self.root/'p.xlsx';w.save(p)
  self.v.ready.remove('po');self.v.read_xlsx(p,'po');self.assertNotIn('po',self.v.ready)
 def test_exclude_config_complete(self):
  c=config_read(Path(__file__).with_name('config.json'));self.assertEqual(len(c['exclude_pop_ids']),382);self.assertEqual(c['exclude_po_ids'],['pay_advance_airtime-of_mg50001']);self.assertNotIn('op_mg50007',c['exclude_pop_ids'])


if __name__=='__main__':unittest.main()
