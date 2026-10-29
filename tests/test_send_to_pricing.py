"""
Send to Pricing (David, 2026-10-28): Pricing sees a request only after a Team
Leader or the Head sends it, which needs every item costed. Before that,
Pricing sees nothing of it: not on its desk, not in its counts, no cost, and
it cannot price it. A cost changed afterwards keeps it with Pricing, flags it
"cost changed" and tells Pricing; pricing it again clears the flag. Rolled
back like test_costing.py.
"""

import unittest

import branding_gate
from test_costing import _CostingHarness


class SendToPricingTest(_CostingHarness):

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        cur.execute("SELECT id FROM rbac_role WHERE code = 'pricing_specialist'")
        self.roles['pricing_specialist'] = cur.fetchone()['id']
        # The grant this change ships, inside the rolled-back transaction
        # (seed_rbac.py writes it for real at deploy).
        cur.execute("INSERT IGNORE INTO permission (code, description) VALUES ('costing.send_to_pricing', 'x')")
        for code in ('operations_manager', 'operations_team_leader'):
            cur.execute("""INSERT IGNORE INTO role_permission (role_id, permission_code, scope)
                           VALUES (%s, 'costing.send_to_pricing', 'all')""", (self.roles[code],))
        cur.execute("INSERT INTO sales_request_items (request_id, name, qty) VALUES (%s, 'Second item', 1)",
                    (self.request_id,))
        self.second_item = cur.lastrowid
        cur.execute("UPDATE sales_request_items SET cost_per_item = 100, total_cost = 400 WHERE id = %s",
                    (self.item_id,))
        cur.close()
        self.pricer = self._make_user('stp-pricer', 'pricing_specialist', None)
        self.sent = []
        self.original_notify = branding_gate.notify_users
        branding_gate.notify_users = lambda ids, title, content, link=None, category=None, action=None: \
            self.sent.append((title, sorted(ids or []), link)) or 1

    def tearDown(self):
        branding_gate.notify_users = self.original_notify
        super().tearDown()

    def _send(self, who):
        return self._client_for(who).post('/api/operations/requests/%d/send-to-pricing' % self.request_id)

    def _desk_ids(self):
        r = self._client_for(self.pricer).get('/api/sales/requests?desk=pricing').get_json()
        return [row['request_id'] for row in r['requests']]

    def _summary_ids(self):
        r = self._client_for(self.pricer).get('/api/pricing/summary').get_json()
        return [int(k) for k in (r.get('by_request') or r.get('requests') or {})]

    def _price(self):
        return self._client_for(self.pricer).post('/api/sales/requests/%d/set-prices' % self.request_id,
                                                  json={'items': [{'item_id': self.item_id, 'sell_per_item': 150}]})

    def test_partly_costed_stays_with_operation(self):
        r = self._send(self.leader)
        self.assertEqual(r.status_code, 400)
        self.assertIn('1 of 2', r.get_json()['error'])
        self.assertNotIn(self.request_id, self._desk_ids())
        self.assertNotIn(self.request_id, self._summary_ids())
        self.assertEqual(self._price().status_code, 400)
        detail = self._client_for(self.pricer).get('/api/sales/requests/%d' % self.request_id).get_json()
        items = detail['request'].get('items') or []
        self.assertTrue(items and all('cost_per_item' not in i for i in items), items[:1])

    def test_leader_sends_when_all_costed_then_pricing_has_it(self):
        cur = self._cursor()
        cur.execute("UPDATE sales_request_items SET cost_per_item = 50, total_cost = 50 WHERE id = %s",
                    (self.second_item,))
        cur.close()
        self.assertEqual(self._send(self.member).status_code, 403)
        r = self._send(self.leader)
        self.assertTrue(r.get_json()['success'], r.get_json())
        self.assertTrue(any('ready for pricing' in t for t, ids, link in self.sent))
        self.assertIn(self.request_id, self._desk_ids())
        self.assertIn(self.request_id, self._summary_ids())
        self.assertEqual(self._send(self.head).status_code, 400)      # already there
        self.assertTrue(self._price().get_json()['success'])

    def test_cost_change_after_handoff_flags_and_tells_pricing(self):
        cur = self._cursor()
        cur.execute("UPDATE sales_request_items SET cost_per_item = 50, total_cost = 50 WHERE id = %s",
                    (self.second_item,))
        cur.close()
        self._send(self.leader)
        self.sent.clear()
        r = self._client_for(self.head).post('/api/operations/requests/add-costs', json={
            'request_id': self.request_id,
            'items': [{'id': self.second_item, 'cost_per_item': 80, 'total_cost': 80}]})
        self.assertTrue(r.get_json()['success'], r.get_json())
        cur = self._cursor()
        cur.execute("SELECT pricing_handoff_at, cost_changed_at FROM sales_request WHERE id = %s", (self.request_id,))
        row = cur.fetchone()
        self.assertIsNotNone(row['pricing_handoff_at'])
        self.assertIsNotNone(row['cost_changed_at'])
        self.assertTrue(any(t.startswith('Cost changed') for t, ids, link in self.sent), self.sent)
        rows = self._client_for(self.pricer).get('/api/sales/requests?desk=pricing').get_json()['requests']
        self.assertTrue([x for x in rows if x['request_id'] == self.request_id][0]['cost_changed'])
        self.assertTrue(self._price().get_json()['success'])
        cur.execute("SELECT cost_changed_at FROM sales_request WHERE id = %s", (self.request_id,))
        self.assertIsNone(cur.fetchone()['cost_changed_at'])
        cur.close()

    def test_cost_change_notice_survives_a_string_request_id(self):
        # The costing form posts the id as text; the notice formats it with %d
        # and was silently dropped (log, 2026-10-29).
        cur = self._cursor()
        cur.execute("UPDATE sales_request_items SET cost_per_item = 50, total_cost = 50 WHERE id = %s",
                    (self.second_item,))
        cur.close()
        self.assertTrue(self._send(self.leader).get_json()['success'])
        self.sent.clear()
        r = self._client_for(self.head).post('/api/operations/requests/add-costs', json={
            'request_id': str(self.request_id),
            'items': [{'id': self.second_item, 'cost_per_item': 90, 'total_cost': 90}]})
        self.assertTrue(r.get_json()['success'], r.get_json())
        self.assertTrue(any(t.startswith('Cost changed') for t, ids, link in self.sent), self.sent)


if __name__ == '__main__':
    unittest.main()
