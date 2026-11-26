import csv
import tempfile
import unittest
from pathlib import Path
from openpyxl import load_workbook
from rule18 import check_mat_codes, read_mat_codes
from validate_po_pop import export_report
from validation_rules import RuleValidator


class Rule18Tests(unittest.TestCase):
    def test_mapping_report_preserves_all_distinct_matches_and_unmatched_rows(self):
        v = RuleValidator({'exclude_po_ids': ['excluded'], 'exclude_pop_ids': []})
        v.ready.add('v')
        v._insert('v', [
            ('v.csv', 'Variant', number, po, vid, '', '', '001')
            for number, (po, vid) in enumerate(
                [('po', '=v1'), ('po', 'v2'), ('po', 'v2'), ('excluded', 'v3')], 2)
        ])
        v.indexes()
        check_mat_codes(v, 'mat_code.csv', [('001', 2), ('1', 3), ('', 4)])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'mapping.xlsx'
            counts = export_report(v, path, 'MAT_CODE', rows_per_sheet=2)
            self.assertEqual(counts, {'Rule 18 Mapping': 3, 'Rule 18 Mapping 2': 3})
            workbook = load_workbook(path, read_only=True)
            try:
                rows = [row for sheet in workbook for row in list(sheet.values)[1:]]
            finally:
                workbook.close()
        self.assertEqual(rows, [
            ('001', '=v1', 'po', 'MATCHED', 2),
            ('001', 'v2', 'po', 'MATCHED', 2),
            ('1', None, None, 'NOT FOUND', 3),
            (None, None, None, 'EMPTY MAT_CODE', 4),
        ])
        self.assertEqual(v.coverage['18_found_rows'], 1)

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
