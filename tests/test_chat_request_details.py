"""
A request chat shows whose request it is and its details -- dates, venue,
template fields -- and never money, for anyone (David, 2026-10-29).
Rolled back like test_costing.py.
"""

import json
import re
import unittest

from test_chat_media import _ChatHarness

MONEY = re.compile(r'cost|sell|price|total|margin|profit|budget', re.I)


def money_in(value):
    """Every key or brief label that talks about money, at any depth."""
    if isinstance(value, dict):
        found = [k for k in value if MONEY.search(k)]
        if MONEY.search(str(value.get('label', ''))):
            found.append(value['label'])
        return found + [m for v in value.values() for m in money_in(v)]
    if isinstance(value, list):
        return [m for v in value for m in money_in(v)]
    return []


class ChatRequestDetailsTest(_ChatHarness):

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        cur.execute("""UPDATE sales_request SET start_date = '2026-11-28', end_date = '2026-12-03',
                       total_cost = 777, total_sell = 999, budget_total = 555, request_data = %s WHERE id = %s""",
                    (json.dumps({'request_types': ['Booth'], 'template_fields': {
                        'Booth_hotel_name': 'InterContinental Citystars', 'Booth_hall_name': 'Saria hall',
                        'Booth_setup_date': '2026-11-29', 'Booth_event_date': '2026-11-30',
                        'Booth_dismantle_date': '2026-12-03', 'Booth_location_governorate': 'Cairo',
                        'Booth_budget': '50000', 'Booth_selling_price': '88888', 'Booth_total_cost': '66666'}}),
                     self.request_id))
        cur.close()

    def _details(self, user):
        return self._client_for(user).get('/api/chat/sr/%d/details' % self.request_id)

    def test_owner_and_participants_get_details_without_money(self):
        for user in (self.seller, self.head):
            r = self._details(user)
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            body = r.get_json()
            self.assertEqual(body['owner']['name'], 'chat-seller')
            self.assertTrue(body['owner']['mobile'])
            pairs = {d['label']: d['value'] for d in body['details']}
            for label, value in (('Start date', '2026-11-28'), ('End date', '2026-12-03'),
                                 ('Setup Date', '2026-11-29'), ('Event Date', '2026-11-30'),
                                 ('Dismantle Date', '2026-12-03'), ('Hotel Name', 'InterContinental Citystars'),
                                 ('Hall Name', 'Saria hall'), ('Location Governorate', 'Cairo')):
                self.assertEqual(pairs.get(label), value, label)
            self.assertEqual(money_in(body), [])
            text = json.dumps(body)
            for amount in ('777', '999', '555', '50000', '88888', '66666'):
                self.assertNotIn(amount, text)

    def test_stranger_is_refused(self):
        self.assertEqual(self._details(self.stranger).status_code, 403)

    def test_list_rows_carry_the_owner(self):
        rows = self._client_for(self.seller).get('/api/chat/sr-list').get_json()['chats']
        row = [c for c in rows if c['request_id'] == self.request_id][0]
        self.assertEqual(row['owner_name'], 'chat-seller')
        self.assertTrue(row['owner_mobile'])


if __name__ == '__main__':
    unittest.main()
