"""
An item's total: price x quantity x days x dimensions, each part counted only
when its Calc box is ticked. Days count for a Sell item too (a screen sold for
a 4-day event), not only for Rent.
"""

import unittest

import branding_gate


class ItemTotalFormulaTest(unittest.TestCase):

    def item(self, **kw):
        base = {'qty': 4, 'sell_type': 'sell', 'rental_days': 4, 'include_days_in_calc': 1,
                'include_qty_in_calc': 1, 'dimension_calc': 'W*H', 'width': 2, 'height': 1.5}
        base.update(kw)
        return base

    def test_sell_counts_ticked_days(self):
        # 4 screens of 2 x 1.5 m for 4 days at 100: 100 x 4 x 4 x 3 = 4,800.
        self.assertEqual(branding_gate.item_total_cost(self.item(), 100), 4800)

    def test_rent_counts_ticked_days(self):
        self.assertEqual(branding_gate.item_total_cost(self.item(sell_type='rent'), 100), 4800)

    def test_unticked_parts_are_left_out(self):
        self.assertEqual(branding_gate.item_total_cost(self.item(include_days_in_calc=0), 100), 1200)
        self.assertEqual(branding_gate.item_total_cost(self.item(include_qty_in_calc=0), 100), 1200)

    def test_one_day_or_missing_dimension_changes_nothing(self):
        self.assertEqual(branding_gate.item_total_cost(self.item(rental_days=1), 100), 1200)
        self.assertEqual(branding_gate.item_total_cost(self.item(height=None), 100), 1600)   # unmeasured: no dimension factor


if __name__ == '__main__':
    unittest.main()
