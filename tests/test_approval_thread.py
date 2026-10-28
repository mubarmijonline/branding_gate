"""
Discussing a pending approval (Beshoy, 2026-10-28): the approver, the
requester, the requester's manager and anyone tagged may read and post;
nobody else; a decided approval keeps its thread readable but closed, and
approving copies it into the new request's comments. Rolled back like
test_costing.py.
"""

import json
import unittest

import branding_gate
from test_costing import _CostingHarness
import fixtures


class ApprovalThreadTest(_CostingHarness):

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        for code in ('sales_head', 'sales_team_leader'):
            cur.execute("SELECT id FROM rbac_role WHERE code = %s", (code,))
            self.roles[code] = cur.fetchone()['id']
        self.approver = self._make_user('thr-approver', 'sales_head', None)
        self.manager = self._make_user('thr-manager', 'sales_team_leader', self.approver)
        self.requester = self._make_user('thr-requester', 'sales_member', self.manager)
        self.outsider = self._make_user('thr-outsider', 'sales_member', None)
        self.tagged = self._make_user('thr-tagged', 'sales_member', None)
        client_id = fixtures.ensure_client(cur)
        cur.execute("""INSERT INTO sales_request_approvals (request_data, requested_by, approval_reason)
                       VALUES (%s, 'thr-requester', 'Urgent date: Request starts in 1 day(s)')""",
                    (json.dumps({'title': 'Vip box', 'client_id': client_id, 'start_date': '2026-10-29',
                                 'request_types': ['Giveaways'], 'template_fields': {}}),))
        self.approval_id = cur.lastrowid
        cur.close()
        self.sent = []
        self.original_notify = branding_gate.notify_users
        branding_gate.notify_users = lambda ids, title, content, link=None, category=None, action=None: \
            self.sent.append((sorted(ids), link)) or len(ids)

    def tearDown(self):
        branding_gate.notify_users = self.original_notify
        super().tearDown()

    def _url(self):
        return '/api/approvals/%d/thread' % self.approval_id

    def _post(self, who, text, tagged=None):
        return self._client_for(who).post(self._url(), json={'comment_text': text, 'mentioned_users': tagged or []})

    def test_approver_asks_requester_and_manager_are_told(self):
        r = self._post(self.approver, 'ليه الطلب ده متأخر؟')
        self.assertEqual(r.status_code, 200, r.get_json())
        others = [ids for ids, link in self.sent if link == '/sales_request?approval=%d' % self.approval_id]
        self.assertEqual(len(others), 1)
        self.assertIn(self.requester, others[0])
        self.assertIn(self.manager, others[0])
        self.assertNotIn(self.approver, others[0] + [i for ids, _ in self.sent for i in ids])

        # The requester answers; the approver who asked hears it on /approvals.
        self.sent.clear()
        self.assertEqual(self._post(self.requester, 'The client confirmed late').status_code, 200)
        to_approvers = [ids for ids, link in self.sent if link == '/approvals?request=%d' % self.approval_id]
        self.assertTrue(to_approvers and self.approver in to_approvers[0])

        thread = self._client_for(self.manager).get(self._url()).get_json()
        self.assertEqual([m['side'] for m in thread['messages']], ['approver', 'requester'])
        self.assertTrue(thread['open'])

        # The card's badge: two messages, last word from the requester.
        pending = self._client_for(self.approver).get('/api/approvals/pending').get_json()['approvals']
        card = [a for a in pending if a['id'] == self.approval_id][0]
        self.assertEqual((card['thread_count'], card['thread_waiting']), (2, False))

    def test_outsiders_are_refused_until_tagged(self):
        self.assertEqual(self._client_for(self.outsider).get(self._url()).status_code, 403)
        self.assertEqual(self._post(self.outsider, 'hi').status_code, 403)
        self.assertEqual(self._client_for(self.member).get(self._url()).status_code, 403)  # Operations
        self._post(self.approver, 'Can you check, @thr-tagged?', [self.tagged])
        self.assertEqual(self._client_for(self.tagged).get(self._url()).status_code, 200)
        self.assertEqual(self._post(self.tagged, 'Checked').status_code, 200)

    def test_deciding_closes_the_thread_and_approving_carries_it_over(self):
        self._post(self.approver, 'Why late?')
        self._post(self.requester, 'Client delay')
        r = self._client_for(self.approver).post('/api/approvals/%d/approve' % self.approval_id, json={})
        self.assertTrue(r.get_json()['success'], r.get_json())
        request_id = r.get_json()['sales_request_id']
        self.assertEqual(self._post(self.requester, 'one more').status_code, 400)
        thread = self._client_for(self.requester).get(self._url()).get_json()
        self.assertEqual((thread['open'], len(thread['messages'])), (False, 2))
        cur = self._cursor()
        cur.execute("SELECT comment_text FROM sales_request_comments WHERE request_id = %s "
                    "AND source = 'approval_discussion' ORDER BY id", (request_id,))
        self.assertEqual([r['comment_text'] for r in cur.fetchall()],
                         ['[Before approval] Why late?', '[Before approval] Client delay'])
        cur.close()

    def test_rejected_is_closed_too(self):
        self._client_for(self.approver).post('/api/approvals/%d/reject' % self.approval_id, json={'reason': 'Too late'})
        self.assertEqual(self._post(self.approver, 'after').status_code, 400)
        self.assertEqual(self._client_for(self.requester).get(self._url()).status_code, 200)


if __name__ == '__main__':
    unittest.main()
