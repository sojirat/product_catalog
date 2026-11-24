import csv
import tempfile
import unittest
import io
import json
import logging
from unittest.mock import patch
from contextlib import redirect_stdout
from pathlib import Path

from rule16 import ID_FILES, check_unique_ids
from validation_rules import RuleValidator


class Rule16Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.old = self.root / 'Old ID'
        self.current = self.root / 'export' / 'csv'
        self.v = RuleValidator({'exclude_po_ids': [], 'exclude_pop_ids': []})
        for folder, prefix, column in ID_FILES:
            self.write(self.old, folder, prefix, column, ['old-rs_mg50001', 'gone-rs_mg50002'])
            self.write(self.current, folder, prefix, column, ['old-rs_mg50001', 'new-rs_mg50003'])

    def write(self, root, folder, prefix, column, ids):
        path = root / folder / (prefix + '_24112026100000.csv')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow([column])
            writer.writerows([value] for value in ids)
        return path

    def check(self):
        check_unique_ids(self.v, self.current, self.old)
        return self.v.issues

    def test_same_ids_and_unmatched_running_numbers_pass(self):
        self.assertEqual(self.check(), [])
        self.assertEqual(self.v.coverage['16_matched_rows'], 6)

    def test_change_in_each_entity_reports_old_and_new_ids(self):
        for folder, prefix, column in ID_FILES:
            self.write(self.current, folder, prefix, column, ['changed-rs_mg50001'])
        issues = self.check()
        self.assertEqual(len(issues), 6)
        self.assertTrue(all(i['severity'] == 'ERROR' and i['expected'] == 'old-rs_mg50001'
                            and i['val'] == 'changed-rs_mg50001' and i['rn'] == 2 for i in issues))

    def test_missing_baseline_is_review(self):
        path = next(self.old.rglob('master_characteristics_*.csv'))
        path.unlink()
        self.assertEqual(self.check()[0]['severity'], 'REVIEW')

    def test_running_comparison_keeps_leading_zeroes(self):
        folder, prefix, column = ID_FILES[0]
        self.write(self.current, folder, prefix, column, ['different-rs_mg050001'])
        self.assertEqual(self.check(), [])

    def test_id_without_trailing_number_is_not_matched(self):
        folder, prefix, column = ID_FILES[0]
        self.write(self.current, folder, prefix, column, ['no-running-number'])
        self.assertEqual(self.check(), [])

    def test_same_running_in_different_entities_is_independent(self):
        folder, prefix, column = ID_FILES[0]
        self.write(self.old, folder, prefix, column, ['characteristic-mh_mg50001'])
        self.write(self.current, folder, prefix, column, ['characteristic-mh_mg50001'])
        self.assertEqual(self.check(), [])

    def test_cli_rule16_report_and_hashes(self):
        from validate_po_pop import main
        from openpyxl import load_workbook
        folder, prefix, column = ID_FILES[0]
        self.write(self.current, folder, prefix, column, ['changed-rs_mg50001'])
        with redirect_stdout(io.StringIO()), patch('logging.FileHandler', return_value=logging.NullHandler()), patch('logging.basicConfig'):
            code = main(['--input-dir', str(self.current.parent), '--rules', '16',
                         '--old-id-dir', str(self.old), '--out', str(self.root / 'results')])
        self.assertEqual(code, 1)
        report_dir = self.root / 'results' / 'check_export'
        summary = json.loads((report_dir / 'summary.json').read_text(encoding='utf-8'))
        self.assertEqual(summary['selected_rules'], [16])
        self.assertEqual(len(summary['input_sha256']), 12)
        workbook = load_workbook(next(report_dir.glob('*ErrorOnly*.xlsx')), read_only=True)
        try:
            self.assertIn('Rule 16 (Errors 1)', workbook.sheetnames)
            self.assertEqual(len(list(workbook['Rule 16 (Errors 1)'].values)), 2)
        finally:
            workbook.close()
