"""
The chat on a sales request: tagging somebody, and telling the people on it.

Two things were broken and both were silent. The comment box read
`/api/users`, which is gated on `user.view` -- an admin permission -- so for
everyone else the list came back 403, stayed empty, and typing `@` offered
nothing. And the mention notification was an INSERT INTO `notifications`, a
MySQL table that does not exist here: the insert raised, the surrounding
`except` swallowed it, and nobody was told anything. Nobody outside the
mentions was told either way.

Rollback-based, like the other route tests here.
"""

import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate
import fixtures


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def close(self): pass


class RequestChatTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4",
                                   use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self._cursor())

        cur = self._cursor()
        cur.execute("SELECT id FROM department WHERE code = 'operations'")
        self.department = cur.fetchone()['id']
        self.roles = {}
        for code in ('operations_manager', 'operations_team_leader',
                     'operations_member', 'account_team_leader'):
            cur.execute("SELECT id FROM rbac_role WHERE code = %s", (code,))
            self.roles[code] = cur.fetchone()['id']

        self.head = self._make_user('chat-head', 'operations_manager')
        self.leader = self._make_user('chat-leader', 'operations_team_leader')
        self.member = self._make_user('chat-member', 'operations_member')
        self.owner = self._make_user('chat-owner', 'account_team_leader')
        self.bystander = self._make_user('chat-bystander', 'operations_team_leader')

        client_id = fixtures.ensure_client(cur)
        cur.execute("""INSERT INTO sales_request (client_id, title, start_date, created_by,
                                                  items_count, owner_user_id)
                       VALUES (%s, 'Chat test request', CURDATE(), 'chat-test', 1, %s)""",
                    (client_id, self.owner))
        self.request_id = cur.lastrowid
        cur.execute("""INSERT INTO sales_request_items (request_id, name, qty)
                       VALUES (%s, 'Chat item', 1)""", (self.request_id,))
        self.item_id = cur.lastrowid
        # The item is with the member, handed down by the leader.
        cur.execute("""INSERT INTO costing_assignment (item_id, request_id, assignee_id,
                                                       assigned_by, status)
                       VALUES (%s, %s, %s, %s, 'open')""",
                    (self.item_id, self.request_id, self.member, self.leader))
        cur.close()

        self.sent = []
        self._real_notify = branding_gate.notify_users

        def capture(user_ids, title, content, link=None):
            self.sent.append({'to': sorted(int(u) for u in (user_ids or []) if u),
                              'title': title, 'content': content, 'link': link})
            return len(user_ids or [])

        branding_gate.notify_users = capture

    def tearDown(self):
        branding_gate.notify_users = self._real_notify
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _make_user(self, username, role_code):
        cur = self._cursor()
        cur.execute("""INSERT INTO user (name, mobile, email, password, username, title,
                                         department_id, rbac_role_id, date)
                       VALUES (%s, %s, %s, 'x', %s, 'Chat Test', %s, %s, NOW())""",
                    (username, '017%08d' % (abs(hash(username)) % 10 ** 8),
                     username + '@example.com', username,
                     self.department, self.roles[role_code]))
        user_id = cur.lastrowid
        cur.close()
        return user_id

    def _client_for(self, user_id):
        perms, role_code = branding_gate.load_permissions(user_id)
        client = branding_gate.app.test_client()
        with client.session_transaction() as flask_session:
            flask_session.update({"user_id": user_id, "mobile": "m", "email": "e",
                                  "username": "u", "name": "Commenter",
                                  "roles": [role_code], "perms": perms,
                                  "role_code": role_code})
        return client

    def _comment(self, actor, text='Anything on this?', mentions=None):
        return self._client_for(actor).post(
            '/api/sales/requests/%d/comments' % self.request_id,
            json={'comment_text': text, 'source': 'general',
                  'mentioned_users': mentions or []})

    def _told(self):
        """Every user id that received something, flattened."""
        out = set()
        for note in self.sent:
            out.update(note['to'])
        return out

    # -- who can be tagged ---------------------------------------------------

    def test_the_mention_list_is_not_an_admin_list(self):
        # This is the whole of the "@ does nothing" report: the box was asking
        # for the account-management list and being refused.
        response = self._client_for(self.head).get('/api/users')
        self.assertEqual(response.status_code, 403)
        response = self._client_for(self.head).get('/api/mention-users')
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertTrue(response.get_json()['users'])

    def test_the_mention_list_carries_no_contact_details(self):
        people = self._client_for(self.head).get(
            '/api/mention-users').get_json()['users']
        for field in ('mobile', 'email', 'password'):
            self.assertNotIn(field, people[0], field)
        self.assertIn('name', people[0])
        self.assertIn('role_name', people[0])

    def test_an_inactive_account_cannot_be_tagged(self):
        cur = self._cursor()
        cur.execute("UPDATE user SET is_active = 0 WHERE id = %s", (self.member,))
        cur.close()
        ids = {p['id'] for p in self._client_for(self.head).get(
            '/api/mention-users').get_json()['users']}
        self.assertNotIn(self.member, ids)

    # -- who hears about a comment ------------------------------------------

    def test_a_comment_reaches_everyone_working_the_request(self):
        response = self._comment(self.head)
        self.assertEqual(response.status_code, 200, response.get_json())
        told = self._told()
        self.assertIn(self.owner, told, 'the person who raised it was not told')
        self.assertIn(self.member, told, 'the person costing it was not told')
        self.assertIn(self.leader, told, 'the leader who assigned it was not told')

    def test_the_author_does_not_notify_themselves(self):
        self._comment(self.head)
        self.assertNotIn(self.head, self._told())

    def test_somebody_with_no_part_in_it_is_left_alone(self):
        self._comment(self.head)
        self.assertNotIn(self.bystander, self._told())

    def test_a_mention_is_its_own_notification(self):
        self._comment(self.head, text='@leader please look', mentions=[self.leader])
        mention_notes = [n for n in self.sent if 'mentioned you' in n['title']]
        self.assertTrue(mention_notes, 'no mention notification: %s' % self.sent)
        self.assertEqual(mention_notes[0]['to'], [self.leader])
        # ...and they do not also get the general one for the same comment.
        general = [n for n in self.sent if 'mentioned you' not in n['title']]
        for note in general:
            self.assertNotIn(self.leader, note['to'])

    def test_every_notification_opens_the_request(self):
        self._comment(self.head, mentions=[self.leader])
        self.assertTrue(self.sent)
        for note in self.sent:
            self.assertEqual(note['link'],
                             '/sales_request?request=%d' % self.request_id)

    def test_someone_who_replied_earlier_stays_in_the_thread(self):
        self._comment(self.leader)          # the leader speaks first
        self.sent = []
        self._comment(self.head)            # then the head replies
        self.assertIn(self.leader, self._told())


if __name__ == '__main__':
    unittest.main()
