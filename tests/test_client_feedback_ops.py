"""
The client's answer on an item reaches the Operations people on the request.

David Osama (Operations Manager), 2026-10-29: Operations costed items and then
never heard whether the client approved, rejected or pushed back on them, and
the cost modal gave no hint either. Deciding now tells the request's costing
people (assignees and assigners, not withdrawn) and the Operations Managers,
never the person recording it and never with an amount; the operations detail
API carries each item's client status for a badge.

Rollback-based, on the costing harness.
"""

import unittest
from unittest import mock

import branding_gate
from test_costing import _CostingHarness


class ClientFeedbackOpsTest(_CostingHarness):

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        cur.execute("SELECT id FROM rbac_role WHERE code = 'admin'")
        self.roles['admin'] = cur.fetchone()['id']
        cur.close()
        self.actor = self._make_user('feedback-admin', 'admin', None)

        self.assertEqual(self._assign(self.head, [self.leader]).status_code, 200)
        self.assertEqual(self._assign(self.leader, [self.member]).status_code, 200)
        cur = self._cursor()
        # The recorder handed one out themselves: still never told.
        cur.execute("""INSERT INTO costing_assignment (item_id, request_id, assignee_id, assigned_by)
                       VALUES (%s, %s, %s, %s)""",
                    (self.item_id, self.request_id, self.member_b, self.actor))
        cur.execute("""INSERT INTO costing_assignment (item_id, request_id, assignee_id, assigned_by, status)
                       VALUES (%s, %s, %s, %s, 'withdrawn')""",
                    (self.item_id, self.request_id, self.outsider, self.leader_b))
        cur.execute("""UPDATE sales_request_items
                       SET cost_per_item = 1234.5, total_cost = 4938, sell_per_item = 9876,
                           total_sell = 39504, approval_status = 'pending'
                       WHERE id = %s""", (self.item_id,))
        cur.close()

        self.sent = []
        patcher = mock.patch.object(
            branding_gate, 'notify_users',
            side_effect=lambda ids, title, body, link=None, **_: self.sent.append(
                {'to': set(ids or []), 'title': title, 'body': body, 'link': link}))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _decide(self, action, payload):
        response = self._client_for(self.actor).post(
            '/api/client-approval/items/%d/%s' % (self.item_id, action), json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        link = '/operation_request?request=%d' % self.request_id
        notices = [n for n in self.sent if n['link'] == link]
        self.assertEqual(len(notices), 1, self.sent)
        return notices[0]

    def _assert_told_right(self, notice, word):
        for person in (self.leader, self.member, self.member_b, self.head):
            self.assertIn(person, notice['to'])
        self.assertNotIn(self.actor, notice['to'])
        self.assertNotIn(self.outsider, notice['to'])
        text = notice['title'] + ' ' + notice['body']
        self.assertIn('Costing test item', text)
        self.assertIn('#%d' % self.request_id, text)
        self.assertIn(word, text)
        for money in ('1234', '1,234', '9876', '9,876', '4938', '39504', '700', 'EGP'):
            self.assertNotIn(money, text)

    def test_approving_tells_the_costing_people_and_the_managers(self):
        notice = self._decide('approve', {'feedback': 'ok at 9876'})
        self._assert_told_right(notice, 'approved')
        # The whole-team notice still goes out, but not twice to the same people.
        for other in self.sent:
            if other is not notice:
                self.assertFalse(other['to'] & notice['to'], other)

    def test_rejecting_tells_them_too(self):
        self._assert_told_right(self._decide('reject', {'feedback': 'too dear'}), 'rejected')

    def test_a_counter_offer_tells_them_without_the_price(self):
        notice = self._decide('negotiate', {'reason': 'cheaper', 'expected_price': 700})
        self._assert_told_right(notice, 'negotiate')

    def _client_status(self):
        response = self._client_for(self.head).get('/api/operations/requests/%d' % self.request_id)
        self.assertEqual(response.status_code, 200)
        item = response.get_json()['request']['items'][0]
        self.assertNotIn('sell_per_item', item)
        self.assertNotIn('is_priced', item)
        return item['client_status']

    def test_the_operations_api_says_where_each_item_stands(self):
        self.assertEqual(self._client_status(), 'waiting')
        self._decide('approve', {})
        self.assertEqual(self._client_status(), 'approved')
        cur = self._cursor()
        cur.execute("UPDATE sales_request_items SET approval_status = 'pending', sell_per_item = NULL "
                    "WHERE id = %s", (self.item_id,))
        cur.close()
        self.assertEqual(self._client_status(), 'not_sent')

    def test_the_status_rules(self):
        status = branding_gate.client_status_of
        self.assertEqual(status({'approval_status': 'rejected'}), 'rejected')
        self.assertEqual(status({'approval_status': 'pending_negotiation'}), 'negotiation')
        self.assertEqual(status({'approval_status': 'pending_negotiation', 'awaiting_recost': 1}),
                         'recosting')
        self.assertEqual(status({'approval_status': 'pending', 'is_priced': 0}), 'not_sent')


if __name__ == '__main__':
    unittest.main()
