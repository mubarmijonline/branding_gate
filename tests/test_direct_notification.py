"""
Admins and heads send a notification to anyone from the notifications panel
(notification.send). Important goes to the Important tab and phones; off, it
is an announcement. Rolled back like test_costing.py; notify_users is caught.
"""

import unittest

import branding_gate
import rbac
from test_costing import _CostingHarness


class DirectNotificationTest(_CostingHarness):

    def setUp(self):
        super().setUp()
        self.sent = []
        self.original = branding_gate.notify_users
        branding_gate.notify_users = lambda ids, title, content, **k: self.sent.append((sorted(ids), title, content, k.get('category'))) or len(ids)

    def tearDown(self):
        branding_gate.notify_users = self.original
        super().tearDown()

    def _send(self, user, **body):
        return self._client_for(user).post('/api/notifications/send', json=body)

    def test_a_head_sends_important(self):
        r = self._send(self.head, user_ids=[self.member, self.leader], title='Stock count', message='Friday 9am')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.sent, [(sorted([self.member, self.leader]), 'Stock count', 'Friday 9am', 'important')])

    def test_announcement_when_not_important(self):
        self._send(self.head, user_ids=[self.member], title='FYI', message='Office closed', important=False)
        self.assertEqual(self.sent[0][3], 'announcement')

    def test_members_and_leaders_cannot(self):
        for user in (self.member, self.leader):
            self.assertEqual(self._send(user, user_ids=[self.head], title='x', message='y').status_code, 403)
        self.assertEqual(self.sent, [])

    def test_validation(self):
        self.assertEqual(self._send(self.head, user_ids=[], title='x', message='y').status_code, 400)
        self.assertEqual(self._send(self.head, user_ids=[self.member], title='', message='y').status_code, 400)
        self.assertEqual(self._send(self.head, user_ids=[self.member], title='x' * 121, message='y').status_code, 400)

    def test_heads_and_executives_hold_it(self):
        for code, (_, _, level) in rbac.ROLES.items():
            held = 'notification.send' in rbac.SEED_MATRIX.get(code, {})
            self.assertEqual(held, level <= rbac.LEVEL_HEAD, code)


if __name__ == '__main__':
    unittest.main()
