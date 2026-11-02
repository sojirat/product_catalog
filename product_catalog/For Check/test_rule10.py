"""Exercise rule 10 from XLSX/CSV input through verified Excel output."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook, load_workbook

from csv_fallback import read_with_fallback
from test_validator import CONFIG
from validate_po_pop import Validator, export_report
from validation_domain import SCHEMAS, CV_DETAIL_FIELDS, CV_DETAIL_HEADERS


class Rule10Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.v = Validator(CONFIG)

    def row(self, po='po1', **changes):
        row = dict(po=po, cid='color', name='Color', val='BLACK',
                   spec_id='spec1', spec_name='Spec', value_type='string', is_default='true')
        row.update(changes)
        return [row[field] for field in SCHEMAS['cv'][2]]

    def csv_file(self, name, rows):
        path = self.root / name
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(SCHEMAS['cv'][1])
            writer.writerows(rows)
        return path

    def check(self):
        self.v.run()
        return [issue for issue in self.v.issues if issue['rule'] == '10']

    def test_duplicate_key_and_full_report_sorted_by_po(self):
        rows = [self.row('po2'), self.row('po1'),
                self.row('po2', spec_id='other', spec_name='Other', is_default='false'),
                self.row('po1'), self.row('unique')]
        self.v.read_cv_files([self.csv_file('PO_Char_Value.csv', rows)])
        self.assertEqual(len(self.check()), 4)
        self.assertEqual(self.v.summary()['rules'][-1]['status'], 'FAIL')
        output = self.root / 'errors.xlsx'
        export_report(self.v, output, 'ERROR')
        workbook = load_workbook(output, read_only=True)
        try:
            self.assertEqual(list(workbook['All'].values),
                             [(CV_DETAIL_HEADERS[0],), ('po1',), ('po2',)])
            detail = list(workbook['Char duplicate detail'].values)
            expected = sorted(self.v.duplicate_cv_rows,
                              key=lambda row: (row['po'], row['id']))
            self.assertEqual(detail, [tuple(CV_DETAIL_HEADERS)] +
                             [tuple(row[field] for field in CV_DETAIL_FIELDS) for row in expected])
            self.assertEqual(len(list(workbook['Rule 10 (Errors 4)'].values)), 5)
        finally:
            workbook.close()

    def test_each_key_field_must_match_exactly(self):
        rows = [self.row()]
        for field, value in [('po', 'po2'), ('cid', 'Color'), ('name', 'color'),
                             ('value_type', 'String'), ('val', 'BLACK ')]:
            changes = {field: value}
            rows.append(self.row(**changes))
        self.v.read_cv_files([self.csv_file('unique.csv', rows)])
        self.assertEqual(self.check(), [])
        self.assertEqual(self.v.summary()['rules'][-1]['status'], 'PASS')

    def test_blank_values_are_ignored_and_exclusions_apply(self):
        rows = [self.row(val=''), self.row(val=''), self.row('excluded'), self.row('excluded'),
                self.row('nonblank'), self.row('nonblank')]
        self.v.ex_po.add('excluded')
        self.v.read_cv_files([self.csv_file('blank.csv', rows)])
        self.assertEqual([issue['po'] for issue in self.check()], ['nonblank', 'nonblank'])
        self.assertEqual(self.v.coverage['10_checked_rows'], 2)
        self.assertEqual([row['po'] for row in self.v.duplicate_cv_rows], ['nonblank', 'nonblank'])
        export_report(self.v, self.root / 'nonblank.xlsx', 'ERROR')
        workbook = load_workbook(self.root / 'nonblank.xlsx', read_only=True)
        try:
            self.assertEqual(list(workbook['All'].values)[1:], [('nonblank',)])
            self.assertEqual([row[6] for row in list(workbook['Char duplicate detail'].values)[1:]],
                             ['BLACK', 'BLACK'])
        finally:
            workbook.close()

    def test_only_blank_values_pass_rule10(self):
        self.v.read_cv_files([self.csv_file('empty.csv', [self.row(val=''), self.row(val='')])])
        self.assertEqual(self.check(), [])
        self.assertEqual(self.v.summary()['rules'][-1]['status'], 'PASS')
        self.assertEqual(self.v.coverage['10_checked_rows'], 0)

    def test_whitespace_is_a_value(self):
        self.v.read_cv_files([self.csv_file('spaces.csv', [self.row(val=' '), self.row(val=' ')])])
        self.assertEqual(len(self.check()), 2)

    def test_duplicate_across_csv_files(self):
        self.v.read_cv_files([self.csv_file('part1.csv', [self.row()]),
                              self.csv_file('part2.csv', [self.row()])])
        self.assertEqual(len(self.check()), 2)

    def test_duplicate_across_split_xlsx_sheets(self):
        workbook = Workbook()
        for index, name in enumerate(['Char_Value', 'Char_Value (2)']):
            sheet = workbook.active if index == 0 else workbook.create_sheet()
            sheet.title = name
            sheet.append(SCHEMAS['cv'][1])
            sheet.append(self.row())
        path = self.root / 'PO.xlsx'
        workbook.save(path)
        self.v.read_xlsx(path, 'cv')
        self.assertEqual(len(self.check()), 2)
        self.assertEqual({r['sheet'] for r in self.v.duplicate_cv_rows}, {'Char_Value', 'Char_Value (2)'})

    def test_missing_sheet_falls_back_to_csv(self):
        workbook = Workbook()
        path = self.root / 'PO.xlsx'
        workbook.save(path)
        csv_path = self.csv_file('PO_Char_Value.csv', [self.row(), self.row()])
        with patch('csv_fallback.find_csv', return_value=csv_path):
            read_with_fallback(self.v, path, 'cv', 'Char_Value', Path('unused.env'))
        self.assertEqual(len(self.check()), 2)
        self.assertEqual({r['src'] for r in self.v.duplicate_cv_rows}, {str(csv_path)})

    def test_missing_value_type_cannot_pass_rule10(self):
        path = self.root / 'missing.csv'
        with path.open('w', encoding='utf-8', newline='') as stream:
            csv.writer(stream).writerow([h for h in SCHEMAS['cv'][1] if h != 'Char Value.valueType'])
        self.v.read_cv_files([path])
        self.check()
        self.assertEqual(self.v.summary()['rules'][-1]['status'], 'INCOMPLETE')


if __name__ == '__main__':
    unittest.main()
