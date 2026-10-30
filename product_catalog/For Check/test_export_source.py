import io
import logging
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from export_source import EXPORT_FILES, discover_export_inputs, latest_export_input, read_export_inputs, resolve_export_input
from validate_po_pop import main


class ExportSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'xlsx'
        for folder, prefix, _ in EXPORT_FILES.values():
            path = self.root / folder / (prefix + '30102026110649.xlsx')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        self.csv = self.root.parent / 'csv' / 'Product Offer' / 'PO_Char_Value_30102026110649.csv'
        self.csv.parent.mkdir(parents=True)
        self.csv.touch()

    def test_discovers_all_tables_and_large_char_value_csv(self):
        sources, cv_paths = discover_export_inputs(self.root)
        self.assertEqual(set(sources), set(EXPORT_FILES))
        self.assertEqual(cv_paths, [self.csv.resolve()])
        validator = Mock()
        env_path = Path('test.env')
        with patch('csv_fallback.read_with_fallback') as reader:
            read_export_inputs(validator, sources, cv_paths, env_path)
        reader.assert_any_call(validator, sources['v'], 'v', 'Product Variants', env_path, on_source=None)
        reader.assert_any_call(validator, sources['t'], 't', 'metaExtension POP', env_path, on_source=None)
        validator.read_cv_files.assert_called_once_with(cv_paths)

    def test_ambiguous_files_require_selection(self):
        (self.root / 'Product Offer' / 'ProductOffer_other.xlsx').touch()
        with self.assertRaisesRegex(ValueError, 'found 2'):
            discover_export_inputs(self.root)

    def test_explicit_char_value_overrides_missing_sibling_csv(self):
        self.csv.unlink()
        override = self.root.parent / 'chosen.csv'
        override.touch()
        _, paths = discover_export_inputs(self.root, [override])
        self.assertEqual(paths, [override.resolve()])

    def test_list_inputs_does_not_read_data_or_create_results(self):
        output = io.StringIO()
        out_dir = self.root.parent / 'should_not_exist'
        with redirect_stdout(output):
            result = main(['--input-dir', str(self.root), '--list-inputs', '--out', str(out_dir)])
        self.assertEqual(result, 0)
        self.assertIn(str(self.csv.resolve()), output.getvalue())
        self.assertFalse(out_dir.exists())

    def test_latest_export_uses_date_not_name_or_modification_time(self):
        export = self.root.parent / 'export'
        newest = export / '01112026090000' / 'xlsx'
        newest.mkdir(parents=True)
        (export / '31102026235959' / 'xlsx').mkdir(parents=True)
        (export / 'notes').mkdir()
        (export / '99999999999999').mkdir()
        (export / '02112026090000').touch()  # Files are not export rounds.
        self.assertEqual(latest_export_input(export), newest.resolve())

    def test_latest_export_does_not_silently_use_older_round(self):
        export = self.root.parent / 'export'
        (export / '30102026110649' / 'xlsx').mkdir(parents=True)
        (export / '31102026110649').mkdir()
        with self.assertRaisesRegex(NotADirectoryError, 'Latest export has no xlsx'):
            latest_export_input(export)

    def test_latest_export_missing_or_empty_directory(self):
        export = self.root.parent / 'export'
        with self.assertRaises(FileNotFoundError):
            latest_export_input(export)
        export.mkdir()
        with self.assertRaisesRegex(ValueError, 'No timestamped export folders'):
            latest_export_input(export)

    def test_latest_export_cli_lists_selected_round(self):
        export = self.root.parent / 'export'
        round_dir = export / '30102026110649'
        round_dir.mkdir(parents=True)
        self.root.rename(round_dir / 'xlsx')
        self.csv.parent.parent.rename(round_dir / 'csv')
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(['--latest-export', str(export), '--list-inputs'])
        self.assertEqual(result, 0)
        self.assertIn(f'Using latest export: {(round_dir / "xlsx").resolve()}', output.getvalue())

    def test_default_cli_uses_latest_project_export(self):
        with patch('export_source.DEFAULT_EXPORT_DIR', self.root.parent), \
             patch('export_source.latest_export_input', return_value=self.root) as latest, \
             redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--list-inputs']), 0)
        latest.assert_called_once_with(self.root.parent)

    def test_named_round_and_explicit_paths_resolve_to_xlsx(self):
        export = self.root.parent / 'export'
        round_dir = export / 'chosen-round'
        round_dir.mkdir(parents=True)
        self.root.rename(round_dir / 'xlsx')
        self.csv.parent.parent.rename(round_dir / 'csv')
        with patch('export_source.DEFAULT_EXPORT_DIR', export):
            for args in (['chosen-round'], ['--input-dir', 'chosen-round'],
                         ['--input-dir', str(round_dir)], ['--input-dir', str(round_dir / 'xlsx')]):
                with self.subTest(args=args), redirect_stdout(io.StringIO()):
                    self.assertEqual(main(args + ['--list-inputs']), 0)
            with self.assertRaises(NotADirectoryError):
                resolve_export_input('missing-round')

    def test_reports_group_by_source_round_and_keep_repeated_runs(self):
        round_dir = self.root.parent / '30102026201519'
        round_dir.mkdir()
        self.root.rename(round_dir / 'xlsx')
        self.csv.parent.parent.rename(round_dir / 'csv')
        output_dir = self.root.parent / 'results'
        with patch('export_source.read_export_inputs'), \
             patch('logging.FileHandler', return_value=logging.NullHandler()), \
             patch('logging.basicConfig'), redirect_stdout(io.StringIO()):
            for _ in range(2):
                main(['--input-dir', str(round_dir), '--out', str(output_dir)])
        reports = list((output_dir / 'check_30102026201519').glob('run_*/summary.txt'))
        self.assertEqual(len(reports), 2)
        self.assertFalse(list(output_dir.glob('run_*')))
