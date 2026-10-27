"""
Group chats: Managers, Operations, Sales. Who is in a room follows role level
and department; outsiders can neither read nor post. Rolled back like
test_costing.py.
"""

import unittest

import branding_gate
from test_costing import _CostingHarness


class GroupChatTest(_CostingHarness):

    def _rooms(self, user_id):
        r = self._client_for(user_id).get('/api/chat/groups')
        self.assertEqual(r.status_code, 200)
        return {g['room']: g for g in r.get_json()['groups']}

    def test_rooms_follow_level_and_department(self):
        # The harness puts everybody in Operations; the head is a manager.
        self.assertEqual(sorted(self._rooms(self.head)), ['managers', 'operations'])
        self.assertEqual(sorted(self._rooms(self.member)), ['operations'])

    def test_a_message_reaches_the_room_and_counts_as_unread(self):
        post = self._client_for(self.member).post('/api/chat/groups/operations/messages',
                                                  json={'comment_text': 'Truck at 9'})
        self.assertEqual(post.status_code, 200, post.get_data(as_text=True))
        self.assertGreaterEqual(self._rooms(self.leader)['operations']['unread'], 1)
        # Your own message is not unread for you.
        before = self._rooms(self.member)['operations']['unread']
        thread = self._client_for(self.leader).get('/api/chat/groups/operations/messages').get_json()
        self.assertEqual(thread['comments'][0]['comment_text'], 'Truck at 9')
        self._client_for(self.leader).post('/api/chat/groups/operations/read')
        self.assertEqual(self._rooms(self.leader)['operations']['unread'], 0)
        self.assertEqual(self._rooms(self.member)['operations']['unread'], before)

    def test_outsiders_can_neither_read_nor_post(self):
        for path in ('/api/chat/groups/managers/messages',):
            self.assertEqual(self._client_for(self.member).get(path).status_code, 403)
            self.assertEqual(self._client_for(self.member).post(path, json={'comment_text': 'hi'}).status_code, 403)
        self.assertEqual(self._client_for(self.member).get('/api/chat/groups/nope/messages').status_code, 404)

    def test_an_empty_message_is_refused(self):
        self.assertEqual(self._client_for(self.member).post(
            '/api/chat/groups/operations/messages', json={'comment_text': '  '}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
