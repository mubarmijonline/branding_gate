"""
My profile (Gamal, 2026-10-30): own details, a password change that needs the
current password, and the latest activity without money. Rolled back like
test_costing.py.
"""

import unittest

from werkzeug.security import generate_password_hash, check_password_hash

from test_costing import _CostingHarness


class ProfileTest(_CostingHarness):

    def setUp(self):
        super().setUp()
        self.me = self._make_user('profile-me', 'sales_member', self.head)
        cur = self._cursor()
        cur.execute("UPDATE user SET password = %s WHERE id = %s",
                    (generate_password_hash('old-secret'), self.me))
        cur.execute("INSERT INTO sales_request_comments (request_id, user_id, comment_text, source) VALUES (%s, %s, 'hi', 'general')",
                    (self.request_id, self.me))
        cur.close()
        self.web = self._client_for(self.me)

    def _stored(self):
        cur = self._cursor()
        cur.execute("SELECT password FROM user WHERE id = %s", (self.me,))
        value = cur.fetchone()['password']
        cur.close()
        return value

    def test_profile_shows_own_details_and_activity(self):
        body = self.web.get('/api/profile').get_json()
        self.assertTrue(body['success'])
        self.assertEqual(body['user']['id'], self.me)
        self.assertNotIn('password', body['user'])
        self.assertIn(('comment', self.request_id), [(a['kind'], a['request_id']) for a in body['activity']])
        self.assertTrue(all(set(a) == {'kind', 'action', 'detail', 'request_id', 'at'} for a in body['activity']))

    def test_password_change_needs_the_current_password(self):
        wrong = self.web.post('/api/profile/password', json={'current': 'nope', 'new': 'brand-new-1'})
        self.assertEqual(wrong.status_code, 403)
        short = self.web.post('/api/profile/password', json={'current': 'old-secret', 'new': 'short'})
        self.assertEqual(short.status_code, 400)
        same = self.web.post('/api/profile/password', json={'current': 'old-secret', 'new': 'old-secret'})
        self.assertEqual(same.status_code, 400)
        self.assertTrue(check_password_hash(self._stored(), 'old-secret'))

        ok = self.web.post('/api/profile/password', json={'current': 'old-secret', 'new': 'brand-new-1'})
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(check_password_hash(self._stored(), 'brand-new-1'))

    def test_page_renders(self):
        self.assertEqual(self.web.get('/profile').status_code, 200)


if __name__ == '__main__':
    unittest.main()
