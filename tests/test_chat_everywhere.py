"""
The CEO (chat.all, held by the admin role) is in every group and every
request chat whatever their department, and cannot be left out (Beshoy,
2026-10-29). Rolled back like test_costing.py.
"""

import unittest

import branding_gate
from test_costing import _CostingHarness


class ChatEverywhereTest(_CostingHarness):

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        cur.execute("SELECT id FROM rbac_role WHERE code = 'admin'")
        self.roles['admin'] = cur.fetchone()['id']
        self.ceo = self._make_user('chat-ceo', 'admin', None)
        cur.execute("UPDATE user SET department_id = (SELECT id FROM department WHERE code = 'executive') "
                    "WHERE id = %s", (self.ceo,))
        cur.close()

    def test_in_every_group(self):
        cur = self._cursor()
        self.assertEqual(branding_gate.chat_rooms_for(cur, self.ceo), list(branding_gate.CHAT_ROOMS))
        for room in branding_gate.CHAT_ROOMS:
            self.assertIn(self.ceo, branding_gate.chat_room_members(cur, room))
        # Not everybody: an Operations member is not in Sales.
        self.assertNotIn(self.member, branding_gate.chat_room_members(cur, 'sales'))
        groups = self._client_for(self.ceo).get('/api/chat/groups').get_json()['groups']
        self.assertEqual([g['room'] for g in groups], list(branding_gate.CHAT_ROOMS))
        self.assertEqual(self._client_for(self.ceo).get('/api/chat/groups/sales/messages').status_code, 200)

    def test_in_every_request_chat(self):
        cur = self._cursor()
        self.assertIn(self.ceo, branding_gate.chat_members(cur, 'sr', self.request_id))
        web = self._client_for(self.ceo)
        self.assertEqual(web.get('/api/sales/requests/%d/comments' % self.request_id).status_code, 200)
        ids = [c['request_id'] for c in web.get('/api/chat/sr-list').get_json()['chats']]
        self.assertIn(self.request_id, ids)


if __name__ == '__main__':
    unittest.main()
