"""
The request's owner in the chats (David, 2026-10-28): the drawer row and the
thread header name the salesperson / Account Manager a request belongs to, the
@ list puts them first, and a search for their name finds their requests.

Also the thread's clock: comment times were serialised by jsonify as "... GMT"
although they are stored as Cairo wall-clock time, so the browser shifted
them again -- a message sent at 21:02 showed as 00:02 the next day.

The pure half runs anywhere; the route half needs the shared MySQL (the
harness from test_chat_media.py, rolled back).
"""

import os
import re
import subprocess
import unittest
from datetime import datetime

import branding_gate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _index():
    rows = [
        {'id': 7, 'name': 'Mona Seller', 'username': '01000000007', 'mobile': '01000000007'},
        {'id': 9, 'name': 'Omar AM', 'username': 'omar', 'mobile': '01000000009'},
        {'id': 11, 'name': '', 'username': '01000000011', 'mobile': '01000000011'},
    ]

    class Cur:
        def execute(self, *a):
            pass

        def fetchall(self):
            return rows
    return branding_gate.people_index(Cur())


class RequestOwnerTest(unittest.TestCase):

    def test_owner_id_wins(self):
        self.assertEqual(branding_gate.request_owner(_index(), 9, '01000000007'),
                         {'user_id': 9, 'name': 'Omar AM'})

    def test_created_by_resolves_as_mobile_name_or_id(self):
        for raw in ('01000000007', 'Mona Seller', 7, '7'):
            self.assertEqual(branding_gate.request_owner(_index(), None, raw)['name'], 'Mona Seller', raw)

    def test_never_a_raw_mobile_or_id(self):
        # Unresolvable, or a person with no name: no name rather than a phone number.
        for owner, created in ((None, '01099999999'), (None, 404), (11, None), (None, None)):
            self.assertIsNone(branding_gate.request_owner(_index(), owner, created)['name'])

    def test_unknown_owner_id_falls_back_to_created_by(self):
        self.assertEqual(branding_gate.request_owner(_index(), 999, 'omar')['user_id'], 9)


class ChatLocalTimeTest(unittest.TestCase):

    def test_local_wall_clock_without_zone(self):
        self.assertEqual(branding_gate.chat_local_time(datetime(2026, 10, 28, 21, 2, 5)), '2026-10-28T21:02:05')
        self.assertIsNone(branding_gate.chat_local_time(None))
        self.assertEqual(branding_gate.chat_local_time('2026-10-28 21:02:05'), '2026-10-28 21:02:05')

    def test_browser_reads_it_as_the_same_wall_clock(self):
        # In Cairo the string must come back as 21:02, not 00:02.
        script = ("var d = new Date('2026-10-28T21:02:05');"
                  "console.log(d.getHours() + ':' + d.getMinutes() + ' ' + d.getDate());")
        try:
            out = subprocess.run(['node', '-e', script], capture_output=True, text=True,
                                 env=dict(os.environ, TZ='Africa/Cairo'), timeout=20).stdout.strip()
        except FileNotFoundError:
            self.skipTest('node not installed')
        self.assertEqual(out, '21:2 28')


class ChatOwnerUiTest(unittest.TestCase):
    """The drawer script carries the owner into the row, the header, search and @."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, 'static', 'js', 'bg-chat.js'), encoding='utf-8') as f:
            cls.js = f.read()

    def test_row_header_search_and_mentions(self):
        self.assertIn("ownerLine(c.owner_name,", self.js)                   # list row
        self.assertIn("ownerLine(cur.owner,", self.js)                      # thread header
        self.assertIn("(c.owner_name || '').toLowerCase().indexOf(q)", self.js)  # search
        self.assertRegex(self.js, r"is_owner \? 1 : 0")                     # @ list, owner first

    def test_owner_name_is_escaped_and_not_translated(self):
        body = re.search(r"function ownerLine\(name, rest\) \{(.*?)\n    \}", self.js, re.S).group(1)
        self.assertIn('esc(name)', body)
        self.assertIn('data-no-i18n', body)

    def test_arabic_label(self):
        with open(os.path.join(ROOT, 'static', 'i18n', 'ar.js'), encoding='utf-8') as f:
            self.assertIn('"Request owner":', f.read())


try:
    from test_chat_media import _ChatHarness
except Exception:  # no MySQLdb / no database here: the pure tests above still run
    _ChatHarness = None


if _ChatHarness is not None:
    class ChatOwnerRoutesTest(_ChatHarness):

        def test_list_names_the_owner(self):
            r = self._client_for(self.seller).get('/api/chat/sr-list')
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            row = [c for c in r.get_json()['chats'] if c['request_id'] == self.request_id][0]
            self.assertEqual(row['owner_user_id'], self.seller)
            self.assertEqual(row['owner_name'], 'chat-seller')

        def test_header_payload_and_owner_first(self):
            r = self._client_for(self.head).get('/api/chat/thread/%s/members' % self.thread)
            body = r.get_json()
            self.assertEqual(body['owner'], {'id': self.seller, 'name': 'chat-seller'})
            self.assertEqual(body['members'][0]['id'], self.seller)
            self.assertTrue(body['members'][0]['is_owner'])
            self.assertEqual(sum(1 for m in body['members'] if m['is_owner']), 1)

        def test_comment_times_are_local_not_gmt(self):
            self.assertEqual(self._post(self.leader, 'hello').status_code, 200)
            stamp = self._messages(self.leader)[0]['created_at']
            self.assertNotIn('GMT', stamp)
            self.assertRegex(stamp, r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$')


if __name__ == '__main__':
    unittest.main()
