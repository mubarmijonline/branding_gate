"""
Editing items until they are costed, and re-costing after (Gamal, 2026-10-30).

An edit is made in place: an item keeps its row, files and costing
assignment. Out for costing is still editable; costed is not, unless Sales asks
for a new cost, which clears cost and price and sends the item back. A request
made through the urgent-date approval keeps its template instances, so the
edit form opens with its items (it opened empty, and adding one looked like
replacing all of them). Rolled back like test_costing.py.
"""

import json
import unittest

import branding_gate
import fixtures
from test_costing import _CostingHarness


class ItemEditRecostTest(_CostingHarness):

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        cur.execute("SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id "
                    "WHERE r.code = 'admin' AND u.is_active = 1 LIMIT 1")
        self.admin = cur.fetchone()['id']
        cur.execute("SELECT client_id FROM sales_request WHERE id = %s", (self.request_id,))
        self.client_id = cur.fetchone()['client_id']
        cur.close()
        self.notified = []
        self.role_notes = []
        self.original = (branding_gate.notify_users, branding_gate.send_notification_to_role)
        branding_gate.notify_users = lambda ids, title, *a, **k: self.notified.append((list(ids), title)) or 1
        branding_gate.send_notification_to_role = lambda role, title, *a, **k: self.role_notes.append((role, title)) or 1

    def tearDown(self):
        branding_gate.notify_users, branding_gate.send_notification_to_role = self.original
        super().tearDown()

    def _sql(self, query, args=()):
        cur = self._cursor()
        cur.execute(query, args)
        rows = cur.fetchall()
        cur.close()
        return rows

    def _item(self, name, qty, item_id=None, **extra):
        item = {'name': name, 'quantity': qty, 'unit': 'pcs', 'comment': '', 'sell_type': 'rent',
                'rental_days': 1, 'include_days_in_calc': True, 'include_qty_in_calc': True,
                'dimension_calc': '', 'request_type': 'Booth', 'instance_id': '1_Booth'}
        if item_id:
            item['id'] = item_id
        item.update(extra)
        return item

    def _edit(self, items):
        payload = {'title': 'Costing test request', 'client_id': str(self.client_id), 'description': '',
                   'start_date': '2026-11-01', 'end_date': '2026-11-02', 'request_types': ['Booth'],
                   'template_fields': {'instances': [{
                       'instance_id': '1_Booth', 'template_id': 1, 'request_type': 'Booth',
                       'fields': {'location': 'Nasr City', 'location_governorate': 'Cairo',
                                  'hotel_name': 'Citystars', 'setup_date': 'TBD'},
                       'items': items}]}}
        r = self._client_for(self.admin).post('/api/sales-requests/update-with-template/%d' % self.request_id,
                                              json=payload)
        self.assertEqual(r.status_code, 200, r.get_json())
        return r.get_json()

    def _cost(self, amount=10, sell=None, sent=False):
        self._sql("UPDATE sales_request_items SET cost_per_item = %s, total_cost = %s, sell_per_item = %s, "
                  "pricing_sent_at = IF(%s, NOW(), NULL) WHERE id = %s",
                  (amount, amount * 4, sell, sent, self.item_id))

    def test_out_for_costing_is_still_editable_in_place(self):
        self._assign(self.head, [self.leader])
        body = self._edit([self._item('Costing test item', 6, self.item_id, comment='bigger')])
        self.assertEqual(body['refused_changes'], [])
        row = self._sql("SELECT id, qty, description FROM sales_request_items WHERE request_id = %s",
                        (self.request_id,))
        self.assertEqual([(r['id'], float(r['qty']), r['description']) for r in row],
                         [(self.item_id, 6.0, 'bigger')])
        self.assertEqual(self._sql("SELECT status FROM costing_assignment WHERE item_id = %s",
                                   (self.item_id,))[0]['status'], 'open')
        self.assertIn(([self.head, self.leader], 'Item changed on request #%06d' % self.request_id), self.notified)

    def test_adding_to_a_fully_costed_request_keeps_every_item(self):
        self._cost(10)
        body = self._edit([self._item('Costing test item', 4, self.item_id), self._item('Extra banner', 2)])
        self.assertEqual(body['refused_changes'], [])
        rows = self._sql("SELECT id, name, cost_per_item FROM sales_request_items WHERE request_id = %s ORDER BY id",
                         (self.request_id,))
        self.assertEqual([r['name'] for r in rows], ['Costing test item', 'Extra banner'])
        self.assertEqual(rows[0]['id'], self.item_id)
        self.assertEqual(float(rows[0]['cost_per_item']), 10.0)
        self.assertIn(('operation', 'New items on request #%06d' % self.request_id), self.role_notes)

    def test_a_costed_item_is_not_changed_without_a_recost(self):
        self._cost(10)
        body = self._edit([self._item('Costing test item', 9, self.item_id)])
        self.assertEqual([(e['name'], e['changes']) for e in body['refused_changes']], [('Costing test item', ['qty'])])
        self.assertEqual(float(self._sql("SELECT qty FROM sales_request_items WHERE id = %s",
                                         (self.item_id,))[0]['qty']), 4.0)
        # Removing it is refused too.
        body = self._edit([self._item('Other', 1)])
        self.assertEqual(body['refused_changes'][0]['changes'], ['removed'])
        self.assertEqual(len(self._sql("SELECT id FROM sales_request_items WHERE id = %s", (self.item_id,))), 1)

    def test_recost_applies_the_change_and_sends_it_back(self):
        self._assign(self.head, [self.leader])
        self._sql("UPDATE costing_assignment SET status = 'closed' WHERE item_id = %s", (self.item_id,))
        self._cost(10, sell=15, sent=True)
        body = self._edit([self._item('Costing test item', 9, self.item_id, recost=True, recost_note='client wants 9')])
        self.assertEqual([r['name'] for r in body['sent_back']], ['Costing test item'])
        row = self._sql("SELECT * FROM sales_request_items WHERE id = %s", (self.item_id,))[0]
        self.assertEqual(float(row['qty']), 9.0)
        self.assertIsNone(row['cost_per_item'])
        self.assertIsNone(row['sell_per_item'])
        self.assertIsNone(row['pricing_sent_at'])
        self.assertIsNotNone(row['recost_requested_at'])
        self.assertEqual(row['recost_note'], 'client wants 9')
        self.assertEqual(self._sql("SELECT status FROM costing_assignment WHERE item_id = %s",
                                   (self.item_id,))[0]['status'], 'open')
        self.assertEqual(self._sql("SELECT action FROM costing_log WHERE item_id = %s ORDER BY id DESC LIMIT 1",
                                   (self.item_id,))[0]['action'], 'recost_requested')
        self.assertIn(('operation', 'Re-cost requested on request #%06d' % self.request_id), self.role_notes)
        # The change log Sales reads carries no money.
        logged = self._sql("SELECT change_description FROM sales_request_change_log WHERE request_id = %s "
                           "AND change_description LIKE %s", (self.request_id, '%sent back to Operations%'))
        self.assertEqual(len(logged), 1)
        self.assertNotIn('10', logged[0]['change_description'].replace('qty 4 -> 9', ''))

        # Costed again by Operations: the mark goes.
        self.assertEqual(self._client_for(self.leader).post('/api/costing/assign', json={
            'item_id': self.item_id, 'assignee_ids': [self.member]}).status_code, 200)
        proposal = self._propose(self.member, 12).get_json()['proposal_id']
        r = self._client_for(self.leader).post('/api/costing/proposals/%d/decide' % proposal,
                                               json={'decision': 'accept'})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertIsNone(self._sql("SELECT recost_requested_at FROM sales_request_items WHERE id = %s",
                                    (self.item_id,))[0]['recost_requested_at'])

    def test_a_client_approved_item_goes_through_negotiation_instead(self):
        self._cost(10, sell=15)
        self._sql("UPDATE sales_request_items SET approval_status = 'approved' WHERE id = %s", (self.item_id,))
        body = self._edit([self._item('Costing test item', 9, self.item_id, recost=True)])
        self.assertEqual(body['sent_back'], [])
        self.assertEqual(body['refused_changes'][0]['reason'], 'with the client')
        self.assertEqual(float(self._sql("SELECT cost_per_item FROM sales_request_items WHERE id = %s",
                                         (self.item_id,))[0]['cost_per_item']), 10.0)

    def test_sales_sees_the_flags_but_no_cost(self):
        owner = self._make_user('recost-sales', 'sales_member', None)
        self._sql("UPDATE sales_request SET owner_user_id = %s WHERE id = %s", (owner, self.request_id))
        self._sql("UPDATE sales_request_items SET recost_requested_at = NOW(), recost_note = 'qty 4 -> 9', "
                  "cost_per_item = NULL WHERE id = %s", (self.item_id,))
        item = self._client_for(owner).get('/api/sales/requests/%d' % self.request_id).get_json()['request']['items'][0]
        self.assertTrue(item['recost_requested'])
        self.assertEqual(item['recost_note'], 'qty 4 -> 9')
        self.assertFalse(item['in_costing'])
        self.assertNotIn('cost_per_item', item)


class UrgentApprovalKeepsInstancesTest(_CostingHarness):

    def test_the_approved_request_opens_with_its_items(self):
        cur = self._cursor()
        cur.execute("SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id "
                    "WHERE r.code = 'admin' AND u.is_active = 1 LIMIT 1")
        admin = cur.fetchone()['id']
        instance = {'instance_id': '2_Printing', 'template_id': 2, 'request_type': 'Printing',
                    'fields': {'delivery_location': 'Nasr City', 'delivery_location_governorate': 'Cairo'},
                    'items': [{'name': 'vinyl', 'quantity': 2, 'unit': 'm', 'width': 2.9, 'height': 2.7,
                               'sell_type': 'sell', 'rental_days': 3, 'dimension_calc': 'W*H',
                               'include_days_in_calc': False, 'request_type': 'Printing'}]}
        cur.execute("INSERT INTO sales_request_approvals (request_type, request_data, requested_by, approval_reason) "
                    "VALUES ('sales_request', %s, 'cost-head', 'Urgent date')",
                    (json.dumps({'title': 'Urgent print', 'client_id': fixtures.ensure_client(cur),
                                 'start_date': '2026-10-31', 'request_types': ['Printing'],
                                 'template_fields': {'instances': [instance], 'flat_fields': {}}}),))
        approval = cur.lastrowid
        cur.close()
        notify = branding_gate.notify_users
        branding_gate.notify_users = lambda *a, **k: 0
        try:
            r = self._client_for(admin).post('/api/approvals/%d/approve' % approval, json={})
        finally:
            branding_gate.notify_users = notify
        self.assertEqual(r.status_code, 200, r.get_json())
        cur = self._cursor()
        cur.execute("SELECT sales_request_id FROM sales_request_approvals WHERE id = %s", (approval,))
        request_id = cur.fetchone()['sales_request_id']
        cur.execute("SELECT sell_type, rental_days, dimension_calc, include_days_in_calc, request_type "
                    "FROM sales_request_items WHERE request_id = %s", (request_id,))
        self.assertEqual(cur.fetchall(), ({'sell_type': 'sell', 'rental_days': 3, 'dimension_calc': 'W*H',
                                           'include_days_in_calc': 0, 'request_type': 'Printing'},))
        cur.close()
        body = self._client_for(admin).get('/api/sales/requests/%d' % request_id).get_json()['request']
        self.assertEqual([len(i['items']) for i in body['template_instances']], [1])
        self.assertEqual(body['template_instances'][0]['fields']['delivery_location'], 'Nasr City')


if __name__ == '__main__':
    unittest.main()
