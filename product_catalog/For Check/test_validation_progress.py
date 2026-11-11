import unittest
from unittest.mock import Mock

from validation_progress import batch_progress
from validation_rules import RuleValidator
from test_validator import CONFIG


class ProgressTests(unittest.TestCase):
    def test_rules_log_order_percent_and_issue_counts(self):
        validator=RuleValidator(CONFIG)
        validator.indexes=Mock()
        for number in range(1,16):
            setattr(validator,f'rule{number}',Mock())
        validator.rule3.side_effect=lambda:validator.add(3,'ERROR','TEST','fixture')
        with self.assertLogs('po_pop',level='INFO') as capture:
            validator.run()
        messages=[record.getMessage() for record in capture.records]
        self.assertIn('25.0%',messages[0])
        starts=[message for message in messages if 'Checking Rule ' in message]
        self.assertEqual(len(starts),15)
        self.assertIn('Checking Rule 1/15',starts[0])
        self.assertIn('Checking Rule 15/15',starts[-1])
        self.assertIn('75.0%',messages[-1])
        self.assertTrue(any('Rule 3/15 finished' in message and 'Error=1' in message for message in messages))

    def test_batch_logs_first_interval_and_last(self):
        with self.assertLogs('po_pop',level='INFO') as capture:
            for number in range(1,206):
                batch_progress('Database SKUs',number,205)
        messages=[record.getMessage() for record in capture.records]
        self.assertEqual(len(messages),4)
        self.assertIn('1/205',messages[0])
        self.assertIn('100/205',messages[1])
        self.assertIn('200/205',messages[2])
        self.assertIn('100.0%',messages[3])


if __name__=='__main__':unittest.main()
