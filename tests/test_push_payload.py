"""
Push is sent data-only (title, body, link). firebase-messaging-sw.js shows it
and opens the link: with a notification block Firebase showed a second copy,
and its fcm_options.link rejects the relative links callers pass -- every
send raised and only the log knew.
"""

import unittest
from unittest import mock

import branding_gate


class PushPayloadTest(unittest.TestCase):

    def test_data_only_with_relative_link(self):
        sent = []
        rows = [{'_id': 1, 'uid': 5, 'fcm_token': 'device-token'}]
        safe = lambda call, fallback=None, label='': {'device tokens': rows, 'badge': 3}.get(label, fallback)
        with mock.patch.object(branding_gate, 'FCM_VAPID_KEY', 'key'), \
             mock.patch.object(branding_gate, 'mongo_safe', safe), \
             mock.patch.object(branding_gate.messaging, 'send', lambda m: sent.append(m) or 'id'):
            n = branding_gate.push_to_users([5], 'Approval Needed', 'SR-1 waits', link='/home?chat=sr:1')
        self.assertEqual(n, 1)
        msg = sent[0]
        self.assertIsNone(msg.notification)
        self.assertEqual(msg.data, {'title': 'Approval Needed', 'body': 'SR-1 waits', 'link': '/home?chat=sr:1',
                                    'badge': '3'})
        self.assertEqual(msg.token, 'device-token')



class PushEverythingTest(unittest.TestCase):
    """Operations phones get every notification; a chat they muted stays quiet."""

    def setUp(self):
        conn, cur = branding_gate.connection()
        try:
            cur.execute("SELECT u.id, d.code FROM user u JOIN department d ON d.id = u.department_id "
                        "WHERE u.is_active = 1")
            rows = cur.fetchall()
        finally:
            cur.close()
            conn.close()
        self.ops = next((r['id'] for r in rows if r['code'] == 'operations'), None)
        self.other = next((r['id'] for r in rows if r['code'] != 'operations'), None)
        if not (self.ops and self.other):
            self.skipTest('needs an Operations user and someone else')

    def test_operations_only(self):
        self.assertEqual(branding_gate.push_everything_ids([self.ops, self.other]), {self.ops})
        self.assertEqual(branding_gate.push_everything_ids([]), set())

    def test_muted_chat_left_out(self):
        thread = 'sr:999999991'
        conn, cur = branding_gate.connection()
        try:
            cur.execute("INSERT INTO chat_mute (user_id, thread, muted_until) VALUES (%s, %s, NULL)",
                        (self.ops, thread))
            conn.commit()
            self.assertEqual(branding_gate.push_everything_ids([self.ops], '/home?chat=' + thread), set())
            self.assertEqual(branding_gate.push_everything_ids([self.ops], '/home?chat=sr:999999992'), {self.ops})
        finally:
            cur.execute("DELETE FROM chat_mute WHERE thread = %s", (thread,))
            conn.commit()
            cur.close()
            conn.close()


if __name__ == '__main__':
    unittest.main()
