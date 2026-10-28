"""
Adding items to a request that already has costed / in-costing items
(Gamal, request 17593): the new item is inserted and goes to Operations, the
costed item is untouched, and an item out for costing keeps its assignment.
Rolled back like test_costing.py.
"""

import unittest

import branding_gate
from test_costing import _CostingHarness


class AddItemsToExistingRequestTest(_CostingHarness):

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        cur.execute("SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id "
                    "WHERE r.code = 'admin' AND u.is_active = 1 LIMIT 1")
        self.admin = cur.fetchone()['id']
        cur.execute("UPDATE sales_request_items SET cost_per_item = 10, total_cost = 40 WHERE id = %s", (self.item_id,))
        cur.execute("INSERT INTO sales_request_items (request_id, name, qty) VALUES (%s, 'Being costed', 2)",
                    (self.request_id,))
        self.in_costing = cur.lastrowid
        cur.execute("INSERT INTO costing_assignment (item_id, request_id, assignee_id, assigned_by) VALUES (%s, %s, %s, %s)",
                    (self.in_costing, self.request_id, self.leader, self.head))
        cur.execute("SELECT client_id FROM sales_request WHERE id = %s", (self.request_id,))
        self.client_id = cur.fetchone()['client_id']
        cur.close()
        self.sent = []
        self.original_notify = branding_gate.send_notification_to_role
        branding_gate.send_notification_to_role = lambda role, title, *a, **k: self.sent.append((role, title)) or 1

    def tearDown(self):
        branding_gate.send_notification_to_role = self.original_notify
        super().tearDown()

    def _item(self, name, qty):
        return {'name': name, 'quantity': qty, 'unit': 'pcs', 'comment': 'note for ' + name, 'sell_type': 'rent',
                'rental_days': 1, 'include_days_in_calc': True, 'include_qty_in_calc': True, 'dimension_calc': '',
                'request_type': 'Booth', 'instance_id': '1_Booth', 'attachments': []}

    def test_a_new_item_lands_and_goes_to_operations(self):
        payload = {'title': 'Costing test request', 'client_id': str(self.client_id), 'description': '',
                   'start_date': '2026-11-01', 'end_date': '2026-11-02', 'request_types': ['Booth'],
                   'template_fields': {'instances': [{'instance_id': '1_Booth', 'template_id': 1, 'request_type': 'Booth',
                                                      'fields': {'location': 'Nasr City', 'location_governorate': 'Cairo',
                                                                 'hotel_name': 'Citystars', 'setup_date': 'TBD'},
                                                      'items': [self._item('Costing test item', 4),
                                                                              self._item('Being costed', 2),
                                                                              self._item('Screen For VIP', 3)]}]}}
        r = self._client_for(self.admin).post('/api/sales-requests/update-with-template/%d' % self.request_id, json=payload)
        body = r.get_json()
        self.assertEqual(r.status_code, 200, body)
        self.assertTrue(body['success'], body)
        self.assertEqual(body['refused_changes'], [])
        cur = self._cursor()
        cur.execute("SELECT id, name, description FROM sales_request_items WHERE request_id = %s ORDER BY id",
                    (self.request_id,))
        rows = cur.fetchall()
        names = [row['name'] for row in rows]
        self.assertEqual(names, ['Costing test item', 'Being costed', 'Screen For VIP'])
        self.assertEqual(rows[0]['id'], self.item_id)            # costed: same row
        self.assertEqual(rows[1]['id'], self.in_costing)         # out for costing: same row
        self.assertEqual(rows[2]['description'], 'note for Screen For VIP')
        cur.execute("SELECT COUNT(*) AS n FROM costing_assignment WHERE item_id = %s AND status = 'open'",
                    (self.in_costing,))
        self.assertEqual(cur.fetchone()['n'], 1)
        cur.close()
        self.assertIn(('operation', 'New items on request #%06d' % self.request_id), self.sent)
        self.assertEqual(branding_gate.notification_category('New items on request #%06d' % self.request_id), 'important')

    def test_payload_shape(self):
        items = branding_gate.submitted_items({'template_fields': {'instances': [{'items': [{'name': 'a'}]}]}})
        self.assertEqual(items, [{'name': 'a'}])


if __name__ == '__main__':
    unittest.main()
