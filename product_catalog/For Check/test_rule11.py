"""Price group must match the single linked POP's single Channel row."""
import unittest
import tempfile
from pathlib import Path

from validation_rules import RuleValidator


class Rule11Tests(unittest.TestCase):
    def setUp(self):
        self.v = RuleValidator({'exclude_po_ids': [], 'exclude_pop_ids': []})
        self.v.ready.update(('v', 'l', 'ch', 'pt'))
        self.insert('v', 'po1', 'v1', 'color,price_group-mh_mg00557,size', 'RED,EUP,L', 'sku1')
        self.insert('l', 'v1', 'pop1')
        self.insert('ch', 'pop1', 'All')
        self.insert('pt', 'pop1', 'Onetime')

    def insert(self, table, *values):
        self.v._insert(table, [('fixture.xlsx', table, len(self.v.rows[table]) + 2, *values)])

    def check(self):
        self.v.indexes()
        self.v.rule11()
        return self.v.issues

    def test_all_eup_at_matching_index_passes(self):
        self.assertEqual(self.check(), [])

    def test_staff_passes(self):
        self.v.rows['ch'][0]['channel'] = 'Web Staff'
        self.v.rows['v'][0]['vals'] = 'RED,STAFF,L'
        self.assertEqual(self.check(), [])

    def test_mismatch_reports_selected_value_and_source(self):
        self.v.rows['v'][0]['vals'] = 'RED,STAFF,L'
        issue, = self.check()
        self.assertEqual((issue['rule'], issue['severity'], issue['val'], issue['expected']),
                         ('11', 'ERROR', 'STAFF', 'EUP'))
        self.assertEqual((issue['vid'], issue['pid'], issue['rn']), ('v1', 'pop1', 2))

    def test_duplicate_link_rows_are_error_even_for_same_pop(self):
        self.insert('l', 'v1', 'pop1')
        self.assertEqual(self.check()[0]['code'], 'PRICE_GROUP_POP_TYPES')

    def test_onetime_and_prebooking_check_every_pop(self):
        self.insert('l', 'v1', 'pop2')
        self.insert('pt', 'pop2', 'Pre-Booking')
        self.insert('ch', 'pop2', 'Web Pre-Booking')
        self.assertEqual(self.check(), [])
        self.v.rows['ch'][1]['channel'] = 'Web Staff'
        self.assertEqual(self.check()[0]['pid'], 'pop2')

    def test_invalid_multi_pop_types(self):
        self.insert('l', 'v1', 'pop2')
        self.insert('pt', 'pop2', 'Pre-Booking')
        for first, second in [('Onetime', 'Onetime'), ('Pre-Booking', 'Pre-Booking'), ('Onetime', 'Other')]:
            with self.subTest(types=(first, second)):
                self.v.rows['pt'][0]['price_type'] = first
                self.v.rows['pt'][1]['price_type'] = second
                self.v.issues = []
                self.assertEqual(self.check()[0]['code'], 'PRICE_GROUP_POP_TYPES')

    def test_multi_pop_missing_master_is_error(self):
        self.insert('l', 'v1', 'missing')
        self.assertEqual(self.check()[0]['code'], 'PRICE_GROUP_PRICE_TYPE_MISSING')

    def test_duplicate_channel_rows_are_error(self):
        self.insert('ch', 'pop1', 'All')
        self.assertEqual(self.check()[0]['reason'], 'POP มีมากกว่า 1 Channel')

    def test_missing_links_and_channels_are_errors(self):
        for table, code in [('l', 'PRICE_GROUP_POP_COUNT'), ('ch', 'PRICE_GROUP_CHANNEL_COUNT')]:
            with self.subTest(table=table):
                saved = self.v.rows[table]
                self.v.rows[table] = []
                self.v.issues = []
                self.assertEqual(self.check()[0]['code'], code)
                self.v.rows[table] = saved

    def test_absent_price_group_skips_even_without_other_inputs(self):
        self.v.rows['v'][0]['cids'] = 'price_group-mh_mg00557suffix'
        self.v.ready = {'v'}
        self.assertEqual(self.check(), [])

    def test_bad_alignment_and_empty_price_are_errors(self):
        for values in ['RED', 'RED,,L']:
            with self.subTest(values=values):
                self.v.rows['v'][0]['vals'] = values
                self.v.issues = []
                self.assertEqual(self.check()[0]['code'], 'PRICE_GROUP_VALUE_INVALID')

    def test_missing_price_type_precedes_channel_check(self):
        for rows in [[], [dict(self.v.rows['pt'][0], price_type='')]]:
            with self.subTest(rows=rows):
                self.v.rows['pt'] = rows
                self.v.issues = []
                self.v.rows['ch'] = []
                self.assertEqual(self.check()[0]['reason'], 'POP ไม่มีข้อมูล priceType')

    def test_channel_price_type_matrix(self):
        for channel, price, value, passes in [
                ('All', 'Onetime', 'EUP', True),
                ('All', 'Pre-Booking', 'EUP', False),
                ('Web Staff', 'Onetime', 'STAFF', True),
                ('Web Staff', 'Pre-Booking', 'STAFF', False),
                ('Web Pre-Booking', 'Pre-Booking', 'EUP', True),
                ('Web Pre-Booking', 'Pre-Booking', 'STAFF', True),
                ('Web Pre-Booking', 'Onetime', 'EUP', False)]:
            with self.subTest(channel=channel, price=price, value=value):
                self.v.rows['ch'][0]['channel'] = channel
                self.v.rows['pt'][0]['price_type'] = price
                self.v.rows['v'][0]['vals'] = 'RED,' + value + ',L'
                self.v.issues = []
                self.assertEqual(not self.check(), passes)

    def test_unknown_channel_needs_review(self):
        self.v.rows['ch'][0]['channel'] = 'Other'
        self.assertEqual(self.check()[0]['severity'], 'REVIEW')

    def test_exclusions(self):
        self.v.ex_po.add('po1')
        self.assertEqual(self.check(), [])
        self.v.ex_po.clear()
        self.v.ex_pop.add('pop1')
        self.assertEqual(self.check(), [])

    def test_channel_workbook_to_rule11_excel_report(self):
        from openpyxl import Workbook, load_workbook
        from validate_po_pop import Validator, export_report
        from test_validator import CONFIG
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'Channel.xlsx'
            output = Path(directory) / 'errors.xlsx'
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = 'Channel'
            sheet.append(['POP_ID', 'ProductOfferPrice.Channel'])
            sheet.append(['pop1', 'Web Staff'])
            workbook.save(source)
            validator = Validator(CONFIG)
            validator.rows['v'] = self.v.rows['v']
            validator.rows['l'] = self.v.rows['l']
            validator.rows['pt'] = self.v.rows['pt']
            validator.ready.update(('v', 'l', 'pt'))
            validator.read_xlsx(source, 'ch', sheet_name='Channel')
            validator.indexes()
            validator.rule11()
            self.assertEqual(validator.issues[0]['expected'], 'STAFF')
            export_report(validator, output, 'ERROR')
            report = load_workbook(output, read_only=True)
            try:
                self.assertIn('Rule 11 (Errors 1)', report.sheetnames)
                self.assertEqual(len(list(report['Rule 11 (Errors 1)'].values)), 2)
            finally:
                report.close()


if __name__ == '__main__':
    unittest.main()
