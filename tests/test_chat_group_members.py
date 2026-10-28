"""
Admin and Heads (chat.group_members) add anyone to a chat group on top of its
rule, and can take out only the ones who were added. Rolled back like
test_costing.py; notify_users is off under unittest.
"""

import unittest

import branding_gate
from test_costing import _CostingHarness


class GroupMembersTest(_CostingHarness):

    def setUp(self):
        super().setUp()
        self.seller = self._make_user('group-seller', 'sales_member', None)
        cur = self._cursor()
        cur.execute("UPDATE user SET department_id = (SELECT id FROM department WHERE code = 'sales') "
                    "WHERE id = %s", (self.seller,))
        cur.close()

    def _add(self, actor, ids):
        return self._client_for(actor).post('/api/chat/groups/operations/members', json={'user_ids': ids})

    def test_only_holders_may_add(self):
        self.assertEqual(self._add(self.member, [self.seller]).status_code, 403)

    def test_add_then_remove(self):
        cur = self._cursor()
        self.assertNotIn('operations', branding_gate.chat_rooms_for(cur, self.seller))
        response = self._add(self.head, [self.seller, self.member])   # member is already in by rule
        self.assertEqual(response.get_json(), {'success': True, 'added': 1})
        self.assertIn('operations', branding_gate.chat_rooms_for(cur, self.seller))
        self.assertIn(self.seller, branding_gate.chat_room_members(cur, 'operations'))

        body = self._client_for(self.head).get('/api/chat/thread/g:operations/members').get_json()
        self.assertTrue(body['can_manage'])
        flags = {m['id']: m['added'] for m in body['members']}
        self.assertTrue(flags[self.seller])
        self.assertFalse(flags[self.member])
        # The seller can now open and read the room.
        self.assertEqual(self._client_for(self.seller).get('/api/chat/groups/operations/messages').status_code, 200)

        rule = self._client_for(self.head).delete('/api/chat/groups/operations/members/%d' % self.member)
        self.assertEqual(rule.status_code, 400)
        gone = self._client_for(self.head).delete('/api/chat/groups/operations/members/%d' % self.seller)
        self.assertEqual(gone.status_code, 200)
        self.assertNotIn('operations', branding_gate.chat_rooms_for(cur, self.seller))

    def test_unknown_room(self):
        self.assertEqual(self._client_for(self.head).post('/api/chat/groups/nope/members',
                                                          json={'user_ids': [self.seller]}).status_code, 404)


if __name__ == '__main__':
    unittest.main()
