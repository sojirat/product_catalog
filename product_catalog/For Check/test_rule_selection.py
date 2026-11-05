import csv
import io
import json
import logging
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import Mock, patch

from test_validator import CONFIG
from validation_rules import RuleValidator
from validation_domain import SCHEMAS, RULE_INPUTS
from validate_po_pop import main
from export_source import discover_export_inputs


class RuleSelectionTests(unittest.TestCase):
    def test_multiple_rules_are_deduplicated_and_only_selected_rules_run(self):
        validator=RuleValidator(CONFIG)
        for number in range(1,15):
            setattr(validator,f'rule{number}',Mock())
        validator.run([14,4,4])
        for number in range(1,15):
            self.assertEqual(getattr(validator,f'rule{number}').call_count, int(number in (4,14)))
        summary=validator.summary()
        self.assertEqual([rule['rule'] for rule in summary['rules']],[4,14])
        self.assertEqual(summary['selected_rules'],[4,14])
        self.assertNotIn(4,summary['skipped_rules'])
        self.assertIn(13,summary['skipped_rules'])

    def test_cli_rule10_only_needs_char_value_csv_and_never_queries_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'round'
            (root/'xlsx').mkdir(parents=True)
            folder=root/'csv'/'Product Offer'
            folder.mkdir(parents=True)
            path=folder/'PO_Char_Value_01012026000000.csv'
            with path.open('w',encoding='utf-8',newline='') as stream:
                writer=csv.writer(stream)
                writer.writerow(SCHEMAS['cv'][1])
                writer.writerow(['po1','color','Color','BLACK','spec1','Spec','string','TRUE'])
                writer.writerow(['po1','color','Color','BLACK','spec1','Spec','string','TRUE'])
            with patch('database_source.open_database') as database, \
                 patch('logging.FileHandler',return_value=logging.NullHandler()), \
                 patch('logging.basicConfig'), redirect_stdout(io.StringIO()):
                exit_code=main(['--input-dir',str(root),'--rules','10','--out',str(Path(directory)/'results')])
            self.assertEqual(exit_code,1)
            database.assert_not_called()
            summary_path=next((Path(directory)/'results').glob('check_*/summary.json'))
            summary=json.loads(summary_path.read_text(encoding='utf-8'))
            self.assertEqual([rule['rule'] for rule in summary['rules']],[10])
            self.assertEqual(summary['source_counts']['cv'],2)
            self.assertEqual(summary['source_counts']['t'],0)

    def test_discovery_for_multiple_rules_does_not_require_unrelated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'xlsx'
            folder=root/'Product Offer Price'
            folder.mkdir(parents=True)
            path=folder/'CharacteristicsForPrice_01012026000000.xlsx'
            path.touch()
            master=folder/'productOfferPrice_01012026000000.xlsx'
            master.touch()
            sources,cv_paths=discover_export_inputs(root,tables=RULE_INPUTS[4] | RULE_INPUTS[5])
            self.assertEqual(sources,{'c':path.resolve(),'m':master.resolve()})
            self.assertEqual(cv_paths,[])

    def test_invalid_rule_is_rejected_before_input_discovery(self):
        for arguments in [['--rules','0'],['--rules','15'],['--rules']]:
            with self.subTest(arguments=arguments), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(arguments)
            self.assertEqual(error.exception.code,2)


if __name__=='__main__':unittest.main()
