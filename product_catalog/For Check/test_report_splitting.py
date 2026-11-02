"""Verify sheet boundaries using small capacities and real XLSX round trips."""
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from test_validator import CONFIG
from validate_po_pop import Validator, export_report, EXCEL_MAX_DATA_ROWS


class ReportSplittingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'report.xlsx'
        self.v = Validator(CONFIG)

    def read_report(self, severity='ERROR', capacity=2):
        counts = export_report(self.v, self.path, severity, rows_per_sheet=capacity)
        workbook = load_workbook(self.path, read_only=True)
        self.addCleanup(workbook.close)
        sheets = {sheet.title: list(sheet.values) for sheet in workbook}
        self.assertEqual(counts, {name: len(rows) for name, rows in sheets.items()})
        self.assertTrue(all(len(rows) <= capacity + 1 for rows in sheets.values()))
        self.assertTrue(all(len(name) <= 31 for name in sheets))
        return sheets

    def test_error_boundaries_and_counts(self):
        for count, expected in [(0, [1]), (2, [3]), (3, [3, 2]), (4, [3, 3]), (5, [3, 3, 2])]:
            with self.subTest(count=count):
                self.v.issues.clear()
                for index in range(count):
                    self.v.add(10, 'ERROR', 'TEST', str(index))
                sheets = self.read_report()
                parts = [rows for name, rows in sheets.items() if name.startswith('Rule 10')]
                self.assertEqual([len(rows) for rows in parts], expected)
                self.assertEqual([row[0] for rows in parts for row in rows[1:]], list(range(1, count+1)))
                for number, rows in enumerate(parts, 1):
                    name = 'Rule 10' + (f' {number}' if number > 1 else '')
                    name += f' (Errors {len(rows)-1})' if count else ' PASS'
                    self.assertIn(name, sheets)

    def test_review_warning_and_input_issues_split_without_losing_rows(self):
        for index in range(5):
            self.v.add(7, 'WARNING' if index % 2 else 'REVIEW', 'TEST', str(index))
            self.v.add('INPUT', 'REVIEW', 'TEST', str(index))
        self.v.add(7, 'ERROR', 'EXCLUDED', 'error only')
        sheets = self.read_report('REVIEW')
        for base in ['Rule 7', 'Input Issues']:
            parts = [sheets[base], sheets[base+' 2'], sheets[base+' 3']]
            self.assertEqual([len(rows) for rows in parts], [3, 3, 2])
            self.assertEqual([row[4] for rows in parts for row in rows[1:]], list(map(str, range(5))))
            self.assertTrue(all(rows[0] == parts[0][0] for rows in parts))

    def test_long_cell_continuations_cross_sheets(self):
        self.v.add(7, 'ERROR', 'TEST', 'long', related='x'*60001)
        sheets = self.read_report()
        rows = sheets['Rule 7 (Errors 2)'][1:] + sheets['Rule 7 2 (Errors 1)'][1:]
        self.assertEqual([row[-1] for row in rows], ['1/3', '2/3', '3/3'])
        self.assertEqual(''.join(row[16] for row in rows), 'x'*60001)

    def test_all_duplicate_details_and_source_evidence_split(self):
        for index in range(5):
            self.v._insert('cv', [('fixture.csv', 'Char_Value', index+2,
                                   f'po{index}', 'cid', 'name', 'value', 'spec', 'Spec', 'string', 'true')])
            self.v.add('9.4', 'ERROR', 'TEST', 'unused', po=f'po{index}', cid='cid', val='value')
        self.v.ready.add('cv')
        self.v.duplicate_cv_rows = self.v.rows['cv']
        for severity in ['ERROR', 'REVIEW']:
            with self.subTest(severity=severity):
                if severity == 'REVIEW':
                    for issue in self.v.issues:
                        issue['severity'] = 'REVIEW'
                sheets = self.read_report(severity)
                bases = ['Rule 9 Sources'] + (['All', 'Char duplicate detail'] if severity == 'ERROR' else [])
                for base in bases:
                    parts = [sheets[base], sheets[base+' 2'], sheets[base+' 3']]
                    self.assertEqual([len(rows) for rows in parts], [3, 3, 2])
                    self.assertTrue(all(rows[0] == parts[0][0] for rows in parts))
                    column = 0 if base != 'Rule 9 Sources' else 4
                    self.assertEqual([row[column] for rows in parts for row in rows[1:]],
                                     [f'po{index}' for index in range(5)])

    def test_invalid_capacities_fail_before_writing(self):
        for capacity in [0, -1, EXCEL_MAX_DATA_ROWS+1, True, 1.5]:
            with self.subTest(capacity=capacity), self.assertRaises(ValueError):
                export_report(self.v, self.path, 'ERROR', rows_per_sheet=capacity)
        self.assertFalse(self.path.exists())


if __name__ == '__main__':
    unittest.main()
