import csv
import tempfile
import unittest
from pathlib import Path
from rule18 import check_mat_codes, read_mat_codes
from validation_rules import RuleValidator


class Rule18Tests(unittest.TestCase):
    def test_exact_matching_and_missing_rows(self):
        v = RuleValidator({'exclude_po_ids': [], 'exclude_pop_ids': []})
        v.ready.add('v')
        v._insert('v', [('v.csv','Variant',2,'po','v1','','','001')])
        v.indexes()
        check_mat_codes(v, 'mat_code.csv', [('001',2), ('1',3), ('001 ',4), ('',5)])
        self.assertEqual([i['sku'] for i in v.issues], ['1','001 ',''])
        self.assertEqual([i['rn'] for i in v.issues], [3,4,5])
        self.assertEqual(v.coverage['18_found_rows'], 1)
        self.assertNotIn(18, v.selected_rules)

    def test_latest_csv_keeps_leading_zeroes(self):
        with tempfile.TemporaryDirectory() as directory:
            for stamp in ['31102026235959','01112026000000']:
                path = Path(directory)/f'mat_code_{stamp}.csv'
                with path.open('w',encoding='utf-8-sig',newline='') as stream:
                    writer=csv.writer(stream);writer.writerow(['MAT_CODE']);writer.writerow(['001'])
            path, rows = read_mat_codes(directory)
            self.assertEqual(path.name, 'mat_code_01112026000000.csv')
            self.assertEqual(rows, [('001',2)])

    def test_missing_input_is_review(self):
        v = RuleValidator({'exclude_po_ids': [], 'exclude_pop_ids': []})
        v.rule18()
        self.assertEqual(v.issues[0]['severity'], 'REVIEW')
