import unittest
import csv
import tempfile
from pathlib import Path
from unittest.mock import Mock
from rule17 import check_pilot
from validation_rules import RuleValidator


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.v = RuleValidator({'exclude_po_ids': [], 'exclude_pop_ids': []})
        self.v.ready.update(('v', 'cv', 'l', 't'))
        self.v._insert('v', [('v.csv', 'Product_Variants', 2, 'po1', 'v1',
                            'model-mh_mg00556,uag_iphone_17_series_casecover_for_device-mh_mg02958',
                            'uagIphone17SeriesCaseCoverForDevice,CASEIPHONE17PRO', 'sku')])
        self.v._insert('cv', [('cv.csv','Char_Value',2,'po1','type','productType','DEVICE','','','',''),
                              ('cv.csv','Char_Value',3,'po1','brand','brand','UAG','','','','')])
        self.v._insert('l', [('l.csv','link',2,'v1','pop1')])
        self.v._insert('t', [('t.csv','meta',2,'pop1','sku','Case','','')])
        self.pilot = [{'No.':'1','Commercial Name':'Case','PRODUCTTYPE':'DEVICE','BRAND':'UAG','MODEL':'CASEIPHONE17PRO'}]

    def test_full_chain_and_camel_snake_matching(self):
        self.v.indexes()
        check_pilot(self.v, self.pilot, 'pilot.csv')
        self.assertEqual(self.v.pilot_matches, [('1','po1','v1','','DEVICE','UAG','CASEIPHONE17PRO')])
        self.assertEqual(self.v.issues, [])

    def test_po_values_must_belong_to_same_candidate(self):
        self.v.rows['cv'][1]['po'] = 'other'
        self.v.indexes()
        check_pilot(self.v, self.pilot, 'pilot.csv')
        self.assertFalse(self.v.pilot_matches)
        self.assertEqual(self.v.issues[0]['severity'], 'ERROR')

    def test_no_pop_or_meta_required_and_commercial_name_ignored(self):
        self.v.ready = {'v', 'cv'}
        self.v.rows['l'] = []
        self.v.rows['t'] = []
        self.pilot[0]['Commercial Name'] = 'Different name'
        self.v.indexes()
        check_pilot(self.v, self.pilot, 'pilot.csv')
        self.assertEqual(self.v.issues, [])
        self.assertEqual(len(self.v.pilot_matches), 1)

    def test_missing_model_marks_later_steps_not_checked(self):
        self.pilot[0]['MODEL'] = 'MISSING'
        self.v.indexes()
        check_pilot(self.v, self.pilot, 'pilot.csv')
        self.assertEqual(self.v.pilot_diagnostics[0][5:8], ('MODEL', 'ไม่พบค่าที่ตรง', 'MISSING'))
        self.assertTrue(all(row[6] == 'ยังไม่ตรวจ' for row in self.v.pilot_diagnostics[1:]))

    def test_brand_failure_reports_actual_value_and_same_po(self):
        self.v.rows['cv'][1]['val'] = 'OTHER'
        self.v.indexes()
        check_pilot(self.v, self.pilot, 'pilot.csv')
        detail = {row[5]: row for row in self.v.pilot_diagnostics}
        self.assertEqual(detail['PRODUCTTYPE'][6], 'พบค่าที่ตรง')
        self.assertEqual(detail['BRAND'][6:9], ('ไม่พบค่าที่ตรง', 'UAG', "'OTHER'"))
        self.assertEqual(detail['BRAND'][2:4], ('po1', 'v1'))
        self.assertEqual(set(detail), {'MODEL', 'PRODUCTTYPE', 'BRAND'})

    def test_default_rules_exclude_special_rule(self):
        self.assertNotIn(17, self.v.selected_rules)
        from validation_domain import DEFAULT_RULE_NUMBERS
        for number in DEFAULT_RULE_NUMBERS:
            setattr(self.v, f'rule{number}', Mock())
        self.v.rule17 = Mock()
        self.v.run()
        self.v.rule17.assert_not_called()

    def test_latest_timestamp_is_calendar_order(self):
        from rule17 import read_pilot, PILOT_HEADERS
        with tempfile.TemporaryDirectory() as directory:
            for timestamp in ('31102026235959', '01112026000000'):
                with (Path(directory) / f'pilot_{timestamp}.csv').open('w', newline='', encoding='utf-8-sig') as stream:
                    writer = csv.writer(stream)
                    writer.writerow(PILOT_HEADERS)
                    writer.writerow(['001', 'Case', 'DEVICE', 'UAG', 'CASEIPHONE17PRO'])
            path, rows = read_pilot(directory)
            self.assertEqual(path.name, 'pilot_01112026000000.csv')
            self.assertEqual(rows[0]['No.'], '001')

    def test_all_matching_pops_export_as_literal_text_and_split(self):
        from rule17 import export_pilot, REPORT_HEADERS
        from openpyxl import load_workbook
        self.v.rows['v'].append(dict(self.v.rows['v'][0], vid='v2', id=2, rn=3))
        self.v._insert('t', [('t.csv','meta',3,'pop2','sku','Case','','')])
        self.v.indexes()
        check_pilot(self.v, self.pilot, 'pilot.csv')
        self.assertEqual(len(self.v.pilot_matches), 2)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'pilot.xlsx'
            self.assertEqual(export_pilot(self.v, path, 1), 2)
            workbook = load_workbook(path, read_only=True)
            try:
                self.assertEqual(workbook.sheetnames, ['Pilot','Pilot 2'])
                self.assertEqual(tuple(next(workbook['Pilot'].values)), REPORT_HEADERS)
            finally:
                workbook.close()
