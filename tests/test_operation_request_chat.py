"""
Operations on the chat of a request they work (David, 2026-10-28): a member
assigned to an item of it, and the leader who assigned them, open, read and
post, and the request is in their drawer; a member who is not assigned gets
403 and does not see it listed. Sales are unchanged. Rolled back like
test_costing.py.
"""

import unittest

import branding_gate
from test_chat_media import _ChatHarness


class OperationRequestChatTest(_ChatHarness):

    def setUp(self):
        super().setUp()
        # The grant this change ships, inside the rolled-back transaction: the
        # shared database is seeded only when the code is deployed.
        cur = self._cursor()
        cur.execute("""INSERT IGNORE INTO role_permission (role_id, permission_code, scope)
                       VALUES (%s, 'sales_request.comment', 'own')""", (self.roles['operations_member'],))
        cur.close()
        self.sent = []
        self.original_notify = branding_gate.notify_users
        branding_gate.notify_users = lambda ids, title, content, link=None, category=None, action=None: \
            self.sent.append((sorted(ids), link)) or len(ids)
        # The leader assigns the request's item to member; member_b and the
        # outsider are not on it.
        r = self._client_for(self.leader).post('/api/costing/assign', json={
            'item_id': self.item_id, 'assignee_ids': [self.member], 'note': ''})
        self.assertEqual(r.status_code, 200, r.get_json())

    def tearDown(self):
        branding_gate.notify_users = self.original_notify
        super().tearDown()

    def _listed(self, user):
        r = self._client_for(user).get('/api/chat/sr-list')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return [c['request_id'] for c in r.get_json()['chats']]

    def test_assigned_member_reads_posts_and_tags_the_seller(self):
        r = self._client_for(self.member).post('/api/sales/requests/%d/comments' % self.request_id,
                                               json={'comment_text': '@chat-seller which colour?',
                                                     'mentioned_users': [self.seller]})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertTrue(any(self.seller in ids and link and str(self.request_id) in link
                            for ids, link in self.sent), self.sent)
        self.assertEqual(len(self._messages(self.member)), 1)
        self.assertIn(self.request_id, self._listed(self.member))
        members = self._client_for(self.member).get('/api/chat/thread/sr:%d/members' % self.request_id)
        self.assertIn(self.member, {m['id'] for m in members.get_json()['members']})

    def test_member_not_assigned_is_refused_and_not_listed(self):
        for user in (self.member_b, self.outsider):
            c = self._client_for(user)
            self.assertEqual(c.get('/api/sales/requests/%d/comments' % self.request_id).status_code, 403)
            self.assertEqual(c.post('/api/sales/requests/%d/comments' % self.request_id,
                                    json={'comment_text': 'hi'}).status_code, 403)
            self.assertEqual(c.get('/api/requests/%d/comments' % self.request_id).status_code, 403)
            self.assertEqual(c.post('/api/chat/sr/%d/mark-read' % self.request_id).status_code, 403)
            self.assertNotIn(self.request_id, self._listed(user))
        members = self._client_for(self.seller).get('/api/chat/thread/sr:%d/members' % self.request_id)
        ids = {m['id'] for m in members.get_json()['members']}
        self.assertNotIn(self.member_b, ids)
        self.assertNotIn(self.outsider, ids)

    def test_leader_who_assigned_opens_it(self):
        self.assertEqual(self._client_for(self.leader).get(
            '/api/sales/requests/%d/comments' % self.request_id).status_code, 200)
        self.assertIn(self.request_id, self._listed(self.leader))

    def test_sales_unchanged(self):
        self.assertIn(self.request_id, self._listed(self.seller))
        self.assertNotIn(self.request_id, self._listed(self.stranger))
        self.assertEqual(self._client_for(self.stranger).get(
            '/api/sales/requests/%d/comments' % self.request_id).status_code, 403)


if __name__ == '__main__':
    unittest.main()
