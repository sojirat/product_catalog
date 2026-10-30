import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from export_source import EXPORT_FILES, discover_export_inputs, read_export_inputs
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
