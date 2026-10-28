"""
Costing sees the whole job (dates, hotel, hall, location...) and never what
it sells for: the brief drops money-named fields, and the request API sends
no selling price at all (David, 2026-10-29).
"""

import json
import unittest
from datetime import date

import branding_gate
from test_costing import _CostingHarness


class CostingBriefTest(unittest.TestCase):

    def test_fields_labelled_and_money_left_out(self):
        brief = branding_gate.costing_brief({
            'title': 'EOA', 'start_date': date(2026, 11, 30), 'priority': 'normal', 'description': '',
            'request_data': json.dumps({'request_types': ['Booth', 'Event'], 'template_fields': {
                'Booth_hotel_name': 'InterContinental Citystars', 'Booth_setup_date': '2026-11-30',
                'Booth_budget': '50000', 'Booth_selling_price': '9', 'nested': {'x': 1}}})})
        pairs = {b['label']: b['value'] for b in brief}
        self.assertEqual(pairs['Title'], 'EOA')
        self.assertEqual(pairs['Start date'], '2026-11-30')
        self.assertEqual(pairs['Booth: Hotel Name'], 'InterContinental Citystars')
        self.assertEqual(pairs['Booth: Setup Date'], '2026-11-30')
        self.assertNotIn('Description', pairs)
        self.assertFalse([l for l in pairs if 'Budget' in l or 'Price' in l or 'Nested' in l])

    def test_bad_request_data_is_no_brief(self):
        self.assertEqual(branding_gate.costing_brief({'request_data': 'not json'}), [])


class CostingApiHasNoSellTest(_CostingHarness):

    def test_no_selling_keys(self):
        cur = self._cursor()
        cur.execute("UPDATE sales_request SET total_sell = 999, request_data = %s WHERE id = %s",
                    (json.dumps({'template_fields': {'Event_hotel_name': 'Hilton'}}), self.request_id))
        cur.execute("UPDATE sales_request_items SET sell_per_item = 9, total_sell = 36 WHERE id = %s", (self.item_id,))
        cur.close()
        req = self._client_for(self.head).get('/api/operations/requests/%d' % self.request_id).get_json()['request']
        self.assertIn({'label': 'Event Hotel Name', 'value': 'Hilton'}, req['brief'])
        sell = lambda d: [k for k in d if 'sell' in k and k != 'sell_type']
        self.assertEqual(sell(req), [])
        self.assertEqual([sell(i) for i in req['items'] if sell(i)], [])
        self.assertNotIn('999', json.dumps(req))
        rows = self._client_for(self.head).get('/api/operations/requests').get_json()['requests']
        self.assertEqual([sell(r) for r in rows if sell(r)], [])


if __name__ == '__main__':
    unittest.main()
