"""
A cost or a selling price of 0 is a real one (David, 2026-11-04): free items.

Some items genuinely cost nothing. Saving 0 used to go through, but every
"is it costed?" check read 0 as no cost, so the item stayed Pending, the cost
box came back empty and Pricing showed "Awaiting Cost". Rolled back like
test_costing.py.
"""

import testdb  # noqa: F401  first: the test database, not the live one
import unittest

import branding_gate
from test_costing import _CostingHarness


class ZeroCostTest(_CostingHarness):

    def setUp(self):
        super().setUp()
        self.original = (branding_gate.notify_users, branding_gate.send_notification_to_role)
        branding_gate.notify_users = lambda *a, **k: 0
        branding_gate.send_notification_to_role = lambda *a, **k: 0

    def tearDown(self):
        branding_gate.notify_users, branding_gate.send_notification_to_role = self.original
        super().tearDown()

    def test_zero_counts_as_costed_everywhere(self):
        client = self._client_for(self.head)
        r = client.post('/api/operations/requests/add-costs', json={
            'request_id': str(self.request_id), 'send_to_pricing': True,
            'items': [{'id': self.item_id, 'cost_per_item': 0, 'total_cost': 0}]})
        body = r.get_json()
        self.assertEqual(r.status_code, 200, body)
        self.assertEqual((body['costed_items'], body['status'], body['sent']), (1, 'Completed', 1))

        listed = [row for row in client.get('/api/operations/requests').get_json()['requests']
                  if row['request_id'] == self.request_id][0]
        self.assertEqual((listed['costed_items_count'], listed['pending_items_count']), (1, 0))

        item = client.get('/api/operations/requests/%d' % self.request_id).get_json()['request']['items'][0]
        self.assertTrue(item['has_cost'])
        self.assertEqual(item['cost_status'], 'Costed')

        item = client.get('/api/sales/requests/%d' % self.request_id).get_json()['request']['items'][0]
        self.assertEqual(item['cost_per_item'], 0.0)

        self.assertEqual(branding_gate.item_lock_reason({'cost_per_item': 0, 'sell_per_item': None}), 'costed')
        self.assertIsNone(branding_gate.item_lock_reason({'cost_per_item': None, 'sell_per_item': None}))

    def test_a_free_item_sells_at_zero(self):
        cur = self._cursor()
        cur.execute("SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id "
                    "WHERE r.code = 'admin' AND u.is_active = 1 LIMIT 1")
        admin = self._client_for(cur.fetchone()['id'])
        cur.execute("UPDATE sales_request_items SET cost_per_item = 0, total_cost = 0, pricing_sent_at = NOW() "
                    "WHERE id = %s", (self.item_id,))
        cur.execute("UPDATE sales_request SET pricing_handoff_at = NOW() WHERE id = %s", (self.request_id,))
        url = '/api/sales/requests/%d/set-prices' % self.request_id
        r = admin.post(url, json={'items': [{'item_id': self.item_id, 'sell_per_item': -5}]})
        self.assertEqual(r.status_code, 400, r.get_json())
        r = admin.post(url, json={'items': [{'item_id': self.item_id, 'sell_per_item': 0}]})
        self.assertEqual(r.status_code, 200, r.get_json())
        cur.execute("SELECT sell_per_item FROM sales_request_items WHERE id = %s", (self.item_id,))
        self.assertEqual(float(cur.fetchone()['sell_per_item']), 0.0)
        cur.close()
        item = admin.get('/api/sales/requests/%d' % self.request_id).get_json()['request']['items'][0]
        self.assertEqual((item['cost_per_item'], item['sell_per_item']), (0.0, 0.0))
        self.assertEqual(branding_gate.item_lock_reason({'cost_per_item': 0, 'sell_per_item': 0}), 'priced')

    def test_a_proposal_of_zero_is_accepted(self):
        self._assign(self.head, [self.leader])
        self.assertEqual(self._client_for(self.leader).post('/api/costing/assign', json={
            'item_id': self.item_id, 'assignee_ids': [self.member]}).status_code, 200)
        proposal = self._propose(self.member, 0).get_json()['proposal_id']
        r = self._client_for(self.leader).post('/api/costing/proposals/%d/decide' % proposal,
                                               json={'decision': 'accept'})
        self.assertEqual(r.status_code, 200, r.get_json())
        cur = self._cursor()
        cur.execute("SELECT cost_per_item FROM sales_request_items WHERE id = %s", (self.item_id,))
        self.assertEqual(float(cur.fetchone()['cost_per_item']), 0.0)
        cur.close()


if __name__ == '__main__':
    unittest.main()
