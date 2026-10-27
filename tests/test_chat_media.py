"""
Chat members, photos, voice notes and seen ticks; plus the smaller fixes that
shipped with them (item photos surviving an edit, cost hidden from Account
Management, who-assigned-whom on the operations board, the storage page).
Rolled back like test_costing.py; uploads go to a temporary folder.
"""

import io
import os
import shutil
import tempfile
import unittest
import wave

from PIL import Image

import branding_gate
from test_costing import _CostingHarness


def _png():
    buf = io.BytesIO()
    Image.new('RGB', (40, 30), (200, 10, 10)).save(buf, 'PNG')
    buf.seek(0)
    return buf


def _wav():
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b'\x00\x00' * 8000)
    buf.seek(0)
    return buf


class _ChatHarness(_CostingHarness):

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp()
        self.original_uploads = branding_gate.UPLOADS_DIR
        branding_gate.UPLOADS_DIR = self.tmp
        cur = self._cursor()
        cur.execute("SELECT id FROM rbac_role WHERE code = 'sales_member'")
        self.roles['sales_member'] = cur.fetchone()['id']
        cur.close()
        self.seller = self._make_user('chat-seller', 'sales_member', None)
        self.stranger = self._make_user('chat-stranger', 'sales_member', None)
        cur = self._cursor()
        cur.execute("UPDATE sales_request SET owner_user_id = %s WHERE id = %s", (self.seller, self.request_id))
        cur.close()
        self.thread = 'sr:%d' % self.request_id

    def tearDown(self):
        branding_gate.UPLOADS_DIR = self.original_uploads
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def _post(self, user, text='', **files):
        return self._client_for(user).post('/api/sales/requests/%d/comments' % self.request_id,
                                           json={'comment_text': text, 'mentioned_users': []})

    def _messages(self, user, **params):
        r = self._client_for(user).get('/api/sales/requests/%d/comments' % self.request_id, query_string=params)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()['comments']


class ChatMembersTest(_ChatHarness):

    def test_request_chat_members_are_who_may_write_in_it(self):
        r = self._client_for(self.head).get('/api/chat/thread/%s/members' % self.thread)
        ids = {m['id'] for m in r.get_json()['members']}
        # The owner, and the Operations ladder that holds comment at 'all'.
        self.assertTrue({self.seller, self.head, self.leader} <= ids)
        # No comment permission; a seller whose own scope does not reach it.
        self.assertNotIn(self.member, ids)
        self.assertNotIn(self.stranger, ids)

    def test_the_mention_list_is_the_chat_only(self):
        r = self._client_for(self.seller).get('/api/mention-users', query_string={'thread': self.thread})
        ids = {u['id'] for u in r.get_json()['users']}
        self.assertIn(self.head, ids)
        self.assertNotIn(self.stranger, ids)
        r = self._client_for(self.seller).get('/api/users/search', query_string={'q': '', 'request_id': self.request_id})
        ids = {u['id'] for u in r.get_json()['users']}
        self.assertIn(self.head, ids)
        self.assertNotIn(self.stranger, ids)

    def test_outsiders_cannot_read_write_or_list(self):
        c = self._client_for(self.stranger)
        self.assertEqual(c.get('/api/sales/requests/%d/comments' % self.request_id).status_code, 403)
        self.assertEqual(c.post('/api/sales/requests/%d/comments' % self.request_id,
                                json={'comment_text': 'hi'}).status_code, 403)
        self.assertEqual(c.get('/api/mention-users', query_string={'thread': self.thread}).status_code, 403)


class SeenTicksTest(_ChatHarness):

    def test_ticks_and_message_info(self):
        self.assertEqual(self._post(self.leader, 'Price by noon').status_code, 200)
        mine = self._messages(self.leader, receipts=1)[0]
        self.assertEqual(mine['receipt'], 'sent')
        # The head opens the chat: seen by some.
        self._messages(self.head, seen=1)
        mine = self._messages(self.leader, receipts=1)[0]
        self.assertEqual(mine['receipt'], 'seen_some')
        self.assertGreaterEqual(mine['seen_count'], 1)
        info = self._client_for(self.leader).get('/api/chat/thread/%s/messages/%d/info' % (self.thread, mine['id']))
        body = info.get_json()
        self.assertIn(self.head, [p['id'] for p in body['seen']])
        self.assertIn(self.leader_b, [p['id'] for p in body['not_seen']])
        self.assertNotIn(self.leader, [p['id'] for p in body['seen'] + body['not_seen']])
        # Info is for the author only.
        self.assertEqual(self._client_for(self.head).get(
            '/api/chat/thread/%s/messages/%d/info' % (self.thread, mine['id'])).status_code, 403)

    def test_reading_without_seen_does_not_mark(self):
        self._post(self.leader, 'x')
        self._messages(self.head)
        self.assertEqual(self._messages(self.leader, receipts=1)[0]['receipt'], 'sent')


class ChatMediaTest(_ChatHarness):

    def test_a_photo_with_a_caption(self):
        r = self._client_for(self.seller).post(
            '/api/sales/requests/%d/comments' % self.request_id,
            data={'kind': 'image', 'comment_text': 'Booth front', 'file': (_png(), 'p.png', 'image/png')},
            content_type='multipart/form-data')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        msg = self._messages(self.seller)[0]
        self.assertEqual(msg['caption'], 'Booth front')
        att = msg['attachments'][0]
        self.assertEqual((att['kind'], att['width'], att['height']), ('image', 40, 30))
        self.assertEqual(self._client_for(self.head).get(att['url']).status_code, 200)
        self.assertEqual(self._client_for(self.stranger).get(att['url']).status_code, 403)

    def test_a_voice_note_becomes_aac(self):
        r = self._client_for(self.seller).post(
            '/api/sales/requests/%d/comments' % self.request_id,
            data={'kind': 'voice', 'duration_ms': '500', 'file': (_wav(), 'v.wav', 'audio/wav')},
            content_type='multipart/form-data')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        msg = self._messages(self.seller)[0]
        self.assertEqual(msg['caption'], '')                      # the stand-in text is not a caption
        self.assertTrue(msg['comment_text'])                      # but lists still have something to show
        att = msg['attachments'][0]
        self.assertEqual((att['kind'], att['mime'], att['duration_ms']), ('voice', 'audio/mp4', 500))

    def test_not_an_image_is_refused(self):
        r = self._client_for(self.seller).post(
            '/api/sales/requests/%d/comments' % self.request_id,
            data={'kind': 'image', 'file': (io.BytesIO(b'not a picture'), 'p.png', 'image/png')},
            content_type='multipart/form-data')
        # The route rolls its insert back (here that also ends the fixture
        # transaction, so the refusal is all there is to check).
        self.assertEqual(r.status_code, 400)
        self.assertIn('photo', r.get_json()['error'])

    def test_group_photo_and_seen(self):
        c = self._client_for(self.member)
        r = c.post('/api/chat/groups/operations/messages',
                   data={'kind': 'image', 'file': (_png(), 'p.png', 'image/png')}, content_type='multipart/form-data')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        rows = self._client_for(self.leader).get('/api/chat/groups/operations/messages',
                                                 query_string={'seen': 1}).get_json()['comments']
        self.assertEqual(rows[0]['attachments'][0]['kind'], 'image')
        mine = c.get('/api/chat/groups/operations/messages').get_json()['comments'][0]
        self.assertIn(mine['receipt'], ('seen_some', 'seen_all'))


class ItemFilesSurviveEditTest(_CostingHarness):

    def test_files_follow_the_reinserted_item(self):
        cur = self._cursor()
        cur.execute("INSERT INTO item_images (item_id, image_path, image_type, file_size) VALUES (%s, %s, 'png', 1)",
                    (self.item_id, 'uploads/items/%d/missing.png' % self.item_id))
        files = branding_gate.snapshot_item_files(cur, self.request_id)
        cur.execute("DELETE FROM sales_request_items WHERE id = %s", (self.item_id,))
        cur.execute("INSERT INTO sales_request_items (request_id, name, qty) VALUES (%s, 'Costing test item', 4)",
                    (self.request_id,))
        new_id = cur.lastrowid
        self.assertEqual(branding_gate.carry_item_files(cur, self.request_id, files), 1)
        cur.execute("SELECT COUNT(*) AS n FROM item_images WHERE item_id = %s", (new_id,))
        self.assertEqual(cur.fetchone()['n'], 1)
        cur.close()


class CostHiddenTest(unittest.TestCase):

    def test_account_management_gets_no_cost(self):
        rows = [{'id': 1, 'cost_per_item': 5, 'total_cost': 20, 'sell_per_item': 9, 'total_sell': 36}]
        with branding_gate.app.test_request_context():
            branding_gate.session['perms'] = {'client_approval.view': 'own'}
            out = branding_gate.hide_item_cost([dict(r) for r in rows])[0]
            self.assertEqual(out, {'id': 1, 'sell_per_item': 9, 'total_sell': 36, 'has_cost': True})
            branding_gate.session['perms'] = {'sales_item.cost': 'all'}
            self.assertEqual(branding_gate.hide_item_cost([dict(r) for r in rows])[0]['total_cost'], 20)


class AssignmentSummaryTest(_CostingHarness):

    def test_the_board_says_who_assigned_whom(self):
        self.assertEqual(self._assign(self.head, [self.leader]).status_code, 200)
        rows = self._client_for(self.head).get('/api/operations/requests').get_json()['requests']
        row = [r for r in rows if r['request_id'] == self.request_id][0]
        self.assertEqual(row['assigned_items_count'], 1)
        self.assertEqual(row['assignments'][0]['items'], 1)
        detail = self._client_for(self.head).get('/api/operations/requests/%d' % self.request_id).get_json()
        self.assertEqual(len(detail['request']['items'][0]['assignments']), 1)


class StorageTest(_CostingHarness):

    def test_admin_only(self):
        cur = self._cursor()
        cur.execute("SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id "
                    "WHERE r.code = 'admin' AND u.is_active = 1 LIMIT 1")
        admin = cur.fetchone()['id']
        cur.close()
        r = self._client_for(admin).get('/api/admin/storage')
        self.assertEqual(r.status_code, 200)
        self.assertIn('uploads_gb', r.get_json())
        self.assertEqual(self._client_for(admin).get('/admin/storage').status_code, 200)
        self.assertEqual(self._client_for(self.head).get('/api/admin/storage').status_code, 403)


if __name__ == '__main__':
    unittest.main()
