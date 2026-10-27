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
        safe = lambda call, fallback=None, label='': rows if label == 'device tokens' else fallback
        with mock.patch.object(branding_gate, 'FCM_VAPID_KEY', 'key'), \
             mock.patch.object(branding_gate, 'mongo_safe', safe), \
             mock.patch.object(branding_gate.messaging, 'send', lambda m: sent.append(m) or 'id'):
            n = branding_gate.push_to_users([5], 'Approval Needed', 'SR-1 waits', link='/home?chat=sr:1')
        self.assertEqual(n, 1)
        msg = sent[0]
        self.assertIsNone(msg.notification)
        self.assertEqual(msg.data, {'title': 'Approval Needed', 'body': 'SR-1 waits', 'link': '/home?chat=sr:1'})
        self.assertEqual(msg.token, 'device-token')


if __name__ == '__main__':
    unittest.main()
