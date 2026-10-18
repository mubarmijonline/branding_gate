"""
Receipts on My Expenses.

Optional photos or documents on an expense line, kept outside the public
uploads/ tree and read through a checked route; shown on the Sales Request
the money was spent on. Rollback-based, with files written to a temp folder.
"""

import io
import os
import shutil
import tempfile
import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass


class ExpenseAttachmentsTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        self.original_dir = branding_gate.EXPENSE_FILES_DIR
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self.raw.cursor(MySQLdb.cursors.DictCursor))
        branding_gate.EXPENSE_FILES_DIR = self.tmp
        branding_gate.app.config['TESTING'] = True

        cur = self._cursor()
        cur.execute("""SELECT u.id, r.code FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
                       WHERE u.is_active = 1 AND r.code IN ('operations_member', 'finance_manager')
                       ORDER BY u.id""")
        rows = cur.fetchall()
        members = [r['id'] for r in rows if r['code'] == 'operations_member']
        self.owner, self.stranger = members[0], members[1]
        self.finance = next(r['id'] for r in rows if r['code'] == 'finance_manager')
        cur.execute("SELECT id, owner_user_id FROM sales_request WHERE owner_user_id IS NOT NULL ORDER BY id LIMIT 1")
        sr = cur.fetchone()
        self.sr_id, self.sr_owner = sr['id'], sr['owner_user_id']
        self.expense = self._expense('draft', self.sr_id)
        self.private_expense = self._expense('draft', None)
        cur.close()

    def _undo(self):
        branding_gate.connection = self.original
        branding_gate.EXPENSE_FILES_DIR = self.original_dir
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    _codes = iter(range(1, 1000))

    def _expense(self, status, sr_id):
        cur = self._cursor()
        code = 'EXP-T7-%d' % next(self._codes)
        cur.execute("""INSERT INTO user_expense_tracking (user_id, tracking_code, supplier_name, sales_request_id,
                       amount, description, expense_date, status)
                       VALUES (%s, %s, 'Transportation', %s, 150, 'Taxi to venue', '2026-10-18', %s)""",
                    (self.owner, code, sr_id, status))
        return cur.lastrowid

    def _web(self, user_id):
        perms, role = branding_gate.load_permissions(user_id)
        web = branding_gate.app.test_client()
        with web.session_transaction() as s:
            s.update({'user_id': user_id, 'mobile': 'm', 'email': 'e', 'username': 'u', 'name': 'T',
                      'roles': [role], 'perms': perms, 'role_code': role})
        return web

    def _upload(self, web, expense_id, *files):
        data = {'files': [(io.BytesIO(body), name) for name, body in files]}
        return web.post('/api/my-expenses/%d/attachments' % expense_id, data=data,
                        content_type='multipart/form-data')

    def test_upload_list_and_open(self):
        web = self._web(self.owner)
        r = self._upload(web, self.expense, ('receipt.jpg', b'\xff\xd8jpeg'), ('invoice.pdf', b'%PDF-1.4'))
        self.assertEqual(r.status_code, 200, r.get_json())
        files = r.get_json()['attachments']
        self.assertEqual([f['name'] for f in files], ['receipt.jpg', 'invoice.pdf'])
        self.assertTrue(all(os.path.realpath(p).startswith(self.tmp) for p in
                            [os.path.join(self.tmp, str(self.expense), n) for n in os.listdir(os.path.join(self.tmp, str(self.expense)))]))
        listed = web.get('/api/my-expenses').get_json()['expenses']
        self.assertEqual(len(next(e for e in listed if e['id'] == self.expense)['attachments']), 2)
        got = web.get(files[0]['url'])
        self.assertEqual((got.status_code, got.data), (200, b'\xff\xd8jpeg'))

    def test_refusals(self):
        web = self._web(self.owner)
        self.assertEqual(self._upload(web, self.expense, ('run.exe', b'MZ')).status_code, 400)
        branding_gate_max = branding_gate.EXPENSE_FILE_MAX_BYTES
        branding_gate.EXPENSE_FILE_MAX_BYTES = 4
        try:
            self.assertEqual(self._upload(web, self.expense, ('big.png', b'12345')).status_code, 400)
        finally:
            branding_gate.EXPENSE_FILE_MAX_BYTES = branding_gate_max
        # Not yours.
        self.assertEqual(self._upload(self._web(self.stranger), self.expense, ('a.png', b'x')).status_code, 404)
        # Decided by Finance: files are kept as they are.
        approved = self._expense('approved', self.sr_id)
        self.assertEqual(self._upload(web, approved, ('a.png', b'x')).status_code, 400)

    def test_who_may_open_a_receipt(self):
        att = self._upload(self._web(self.owner), self.private_expense, ('r.png', b'png')).get_json()['attachments'][0]
        self.assertEqual(self._web(self.finance).get(att['url']).status_code, 200)     # approver
        self.assertEqual(self._web(self.stranger).get(att['url']).status_code, 403)    # no reach, no request

    def test_request_shows_sent_expenses_with_receipts(self):
        web = self._web(self.owner)
        self._upload(web, self.expense, ('r.png', b'png'))
        sr_web = self._web(self.sr_owner)
        res = sr_web.get('/api/sales/requests/%d/expenses' % self.sr_id).get_json()
        self.assertNotIn(self.expense, [e['id'] for e in res['expenses']])            # draft: not yet sent
        cur = self._cursor()
        cur.execute("UPDATE user_expense_tracking SET status = 'submitted' WHERE id = %s", (self.expense,))
        res = sr_web.get('/api/sales/requests/%d/expenses' % self.sr_id).get_json()
        mine = next(e for e in res['expenses'] if e['id'] == self.expense)
        self.assertEqual((len(mine['attachments']), mine['supplier']), (1, 'Transportation'))
        self.assertGreaterEqual(res['totals']['pending'], 150.0)
        self.assertEqual(sr_web.get(mine['attachments'][0]['url']).status_code, 200)  # request viewer

    def test_remove_file_and_delete_expense_cleans_up(self):
        web = self._web(self.owner)
        att = self._upload(web, self.expense, ('a.png', b'1'), ('b.png', b'2')).get_json()['attachments']
        self.assertEqual(web.delete('/api/my-expenses/attachments/%d' % att[0]['id']).status_code, 200)
        self.assertEqual(self._web(self.stranger).delete('/api/my-expenses/attachments/%d' % att[1]['id']).status_code, 404)
        self.assertEqual(len(os.listdir(os.path.join(self.tmp, str(self.expense)))), 1)
        self.assertEqual(web.delete('/api/my-expenses/%d' % self.expense).status_code, 200)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, str(self.expense))))


if __name__ == '__main__':
    unittest.main()
