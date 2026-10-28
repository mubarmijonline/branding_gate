"""
Save Prices on the price window (Gamal, 2026-10-28): every row saves itself as
it is edited, so the button must wait for those saves and then close with
"Saved" -- not warn "set or change at least one selling price" over a request
that is already priced. Behaviour checked in the browser; this pins the shape.
"""

import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = open(os.path.join(HERE, '..', 'templates', 'sales_request.html'), encoding='utf-8').read()


class SavePricesButtonTest(unittest.TestCase):

    def test_waits_for_row_saves_then_closes_saved(self):
        handler = PAGE[PAGE.index("$('#savePricesBtn').click("):]
        handler = handler[:handler.index('function closeSavedPrices')]
        self.assertIn('flushPriceEdits()', handler)
        self.assertIn('saveRemainingPrices()', handler)

    def test_nothing_left_to_send_on_a_priced_request_is_saved_not_a_warning(self):
        body = PAGE[PAGE.index('function saveRemainingPrices'):]
        body = body[:body.index('$.ajax(')]
        self.assertRegex(body, r'if \(priced\) \{ closeSavedPrices\(\); return; \}')
        self.assertNotIn('set or change at least one', PAGE)


if __name__ == '__main__':
    unittest.main()
