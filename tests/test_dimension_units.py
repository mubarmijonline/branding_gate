"""
Dimensions are metres, in one unit, everywhere.

The form used to take centimetres and divide by 100 on the way in while the edit
form loaded the stored metres back into the same box, so every re-save shrank
the item another hundredfold. Nothing converts any more, and these tests fail if
a conversion or a centimetre label comes back.
"""

import os
import unittest

import fix_dimension_units as fix


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ITEM_TEMPLATES = ('sales_request.html', 'operation_request.html', 'approved_items.html')


def _read(name):
    with open(os.path.join(ROOT, 'templates', name), encoding='utf-8') as handle:
        return handle.read()


class UnitSurfaceTest(unittest.TestCase):

    def test_no_page_labels_an_item_dimension_in_centimetres(self):
        for name in ITEM_TEMPLATES:
            body = _read(name)
            for label in ('Width (cm)', 'Height (cm)', 'Depth (cm)',
                          "+ 'cm'", '}cm', 'centimeters'):
                self.assertNotIn(label, body, '%s still says %s' % (name, label))

    def test_the_form_stores_what_was_typed(self):
        body = _read('sales_request.html')
        for conversion in ('parseFloat(itemWidth) / 100',
                           'parseFloat(itemHeight) / 100',
                           'parseFloat(itemDepth) / 100'):
            self.assertNotIn(conversion, body)
        self.assertIn('Enter dimensions in metres (m)', body)

    def test_the_edit_form_does_not_guess_the_unit_on_the_way_in(self):
        # A heuristic used to multiply by 100 only when the value was 10 or
        # less, so what an edit saved depended on the size of the item.
        self.assertNotIn('_mToCm', _read('sales_request.html'))


class RescaleDecisionTest(unittest.TestCase):
    """Which stored rows are wrong, and by how much."""

    def test_metre_sized_rows_are_left_alone(self):
        for values in ([1.5, 4.0], [5.0, 5.0, 2.0], [0.6, 11.0], [3.0]):
            self.assertIsNone(fix.scale_for(values), values)

    def test_hundreds_are_centimetres(self):
        self.assertEqual(fix.scale_for([300.0, 600.0]), 0.01)
        self.assertEqual(fix.scale_for([500.0, 500.0]), 0.01)

    def test_hundredths_were_divided_twice(self):
        self.assertEqual(fix.scale_for([0.015, 0.04]), 100.0)

    def test_an_empty_or_unmeasured_row_is_left_alone(self):
        self.assertIsNone(fix.scale_for([]))
        self.assertIsNone(fix.scale_for([None, None]))

    def test_only_the_dimensions_the_item_multiplies_are_read(self):
        # A stray depth says nothing about the size of a width x height item.
        self.assertEqual(fix.used_dimensions('W*H'), ['width', 'height'])
        self.assertEqual(fix.used_dimensions('W*H*D'), ['width', 'height', 'depth'])
        self.assertEqual(fix.used_dimensions(''), [])

    def test_a_row_that_stays_implausible_is_left_for_a_human(self):
        row = {
            'attributes': '{"width": "300.0", "height": "10000.0"}',
            'dimension_calc': 'W*H',
        }
        scale, updated, note = fix.plan_row(row)
        self.assertIsNone(scale)
        self.assertIsNone(updated)
        self.assertIn('too big', note)

    def test_a_correctable_row_is_rescaled_whole(self):
        row = {
            'attributes': '{"width": "500.0", "height": "500.0", "depth": "200.0"}',
            'dimension_calc': 'W*H',
        }
        scale, updated, note = fix.plan_row(row)
        self.assertIsNone(note)
        self.assertEqual(scale, 0.01)
        # The unused depth moves too, so the row does not end up half converted.
        self.assertEqual((updated['width'], updated['height'], updated['depth']),
                         (5.0, 5.0, 2.0))


if __name__ == '__main__':
    unittest.main()
