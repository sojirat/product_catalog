import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from openpyxl import Workbook

from validation_domain import DEFAULT_RULE_NUMBERS
from validate_po_pop import Validator


class Rule19Tests(unittest.TestCase):
    def test_checks_every_product_offer_against_category_in_same_workbook(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'Product Offer.xlsx'
            workbook = Workbook()
            workbook.active.title = 'ProductOffer'
            for row in (['Product Id'], ['001'], ['002'], ['003']):
                workbook.active.append(row)
            category = workbook.create_sheet('Category')
            for row in (['PO_ID', 'category_id'], ['001', 'a'], ['001', 'b'], ['003', 'c']):
                category.append(row)
            workbook.save(path)

            validator = Validator({'exclude_po_ids': ['002'], 'exclude_pop_ids': []})
            validator.read_xlsx(path, 'po')
            validator.read_xlsx(path, 'cat')
            validator.run([19])

        self.assertIn(19, DEFAULT_RULE_NUMBERS)
        self.assertEqual(
            [(issue['severity'], issue['po'], issue['rn']) for issue in validator.issues],
            [('ERROR', '002', 3)],
        )
