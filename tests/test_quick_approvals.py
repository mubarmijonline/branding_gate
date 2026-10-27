"""
Deciding an approval from its notification: the state the tray shows, the
details modal, and that the modal's buttons are the approval page's own
endpoints. Rolled back like test_costing.py.
"""

import unittest

import branding_gate
from test_costing import _CostingHarness


class QuickStateTest(unittest.TestCase):

    def test_states_follow_the_stage(self):
        state = branding_gate.quick_state
        manager = {'kind': 'custody', 'stage': 'manager'}
        finance = {'kind': 'custody', 'stage': 'finance'}
        self.assertEqual(state(manager, 'pending_manager'), 'pending')
        # Passed on to Finance: done, as far as the manager is concerned.
        self.assertEqual(state(manager, 'pending_finance'), 'approved')
        self.assertEqual(state(finance, 'pending_finance'), 'pending')
        self.assertEqual(state(finance, 'rejected'), 'declined')
        self.assertEqual(state({'kind': 'negotiation'}, 'sales_head_declined'), 'declined')
        self.assertEqual(state({'kind': 'party_request'}, 'pending_admin'), 'pending')
        self.assertEqual(state({'kind': 'party_request'}, 'cancelled'), 'cancelled')
        self.assertEqual(state(manager, None), 'gone')


class QuickCustodyTest(_CostingHarness):

    def _ask(self):
        r = self._client_for(self.member).post('/api/finance/request-balance', json={
            'amount': 750, 'description': 'Quick approval test'})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        cur = self._cursor()
        cur.execute("SELECT id, status FROM user_balance_transfers WHERE to_user_id = %s ORDER BY id DESC LIMIT 1",
                    (self.member,))
        row = cur.fetchone()
        cur.close()
        self.assertEqual(row['status'], 'pending_manager')
        return row['id']

    def _details(self, actor, transfer_id):
        return self._client_for(actor).get(
            '/api/quick-approvals/custody/%d?stage=manager' % transfer_id).get_json()

    def test_the_leader_sees_it_waiting_and_approves_through_the_page_endpoint(self):
        transfer_id = self._ask()
        counts = self._client_for(self.leader).get('/api/approvals/waiting-counts').get_json()['counts']
        self.assertGreaterEqual(counts['expenses'], 1)
        details = self._details(self.leader, transfer_id)
        self.assertTrue(details['quick'])
        self.assertEqual(details['amount'], 750.0)
        self.assertEqual(details['approve_url'],
                         '/api/finance/balance-requests/%d/manager-approve' % transfer_id)
        r = self._client_for(self.leader).post(details['approve_url'], json={'notes': 'ok', 'amount': 700})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        after = self._details(self.leader, transfer_id)
        self.assertEqual(after['state'], 'approved')
        self.assertFalse(after['quick'])

    def test_declining_needs_a_reason_and_shows_declined(self):
        transfer_id = self._ask()
        url = self._details(self.leader, transfer_id)['reject_url']
        self.assertEqual(self._client_for(self.leader).post(url, json={'reason': ''}).status_code, 400)
        self.assertEqual(self._client_for(self.leader).post(url, json={'reason': 'No'}).status_code, 200)
        self.assertEqual(self._details(self.leader, transfer_id)['state'], 'declined')

    def test_someone_off_the_line_is_refused_by_the_same_rule(self):
        transfer_id = self._ask()
        url = self._details(self.leader, transfer_id)['approve_url']
        self.assertNotEqual(self._client_for(self.leader_b).post(url, json={}).status_code, 200)

    def test_people_without_the_permission_cannot_read_it(self):
        transfer_id = self._ask()
        self.assertEqual(self._client_for(self.member_b).get(
            '/api/quick-approvals/custody/%d?stage=manager' % transfer_id).status_code, 403)


if __name__ == '__main__':
    unittest.main()
