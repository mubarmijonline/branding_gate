"""
Uploaded files sit behind the login.

nginx served uploads/ to anyone with a link. Every file now comes through
/uploads/<path>, which wants a session and a permission that reaches the
record the file belongs to. Rollback-based, with files in a temp folder.
"""

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
    def close(self): pass


class UploadsProtectedTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        self.original_dir = branding_gate.UPLOADS_DIR
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self.raw.cursor(MySQLdb.cursors.DictCursor))
        branding_gate.UPLOADS_DIR = self.tmp
        branding_gate.app.config['TESTING'] = True

        cur = self.raw.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("""SELECT i.id AS item_id, r.id AS request_id, r.owner_user_id
                       FROM sales_request_items i JOIN sales_request r ON r.id = i.request_id
                       WHERE r.owner_user_id IS NOT NULL ORDER BY i.id LIMIT 1""")
        row = cur.fetchone()
        self.item_id, self.request_id, self.request_owner = row['item_id'], row['request_id'], row['owner_user_id']
        self.users = {}
        for role in ('finance_member', 'sales_member', 'operations_member'):
            cur.execute("""SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
                           WHERE r.code = %s AND u.is_active = 1 AND u.id <> %s ORDER BY u.id LIMIT 1""",
                        (role, self.request_owner))
            found = cur.fetchone()
            self.users[role] = found['id'] if found else None
        cur.close()
        self._write('items/%d/receipt.png' % self.item_id, b'png-bytes')
        self._write('companies/9/doc.pdf', b'%PDF')
        self._write('notes/secret.txt', b'nope')

    def _undo(self):
        branding_gate.connection = self.original
        branding_gate.UPLOADS_DIR = self.original_dir
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.raw.rollback()
        self.raw.close()

    def _write(self, rel, body):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(body)

    def _web(self, user_id=None):
        web = branding_gate.app.test_client()
        if user_id:
            perms, role = branding_gate.load_permissions(user_id)
            with web.session_transaction() as s:
                s.update({'user_id': user_id, 'mobile': 'm', 'email': 'e', 'username': 'u', 'name': 'T',
                          'roles': [role], 'perms': perms, 'role_code': role})
        return web

    def test_no_login_no_file(self):
        r = self._web().get('/uploads/items/%d/receipt.png' % self.item_id)
        self.assertIn(r.status_code, (302, 401))

    def test_request_owner_and_item_desks_get_item_files(self):
        url = '/uploads/items/%d/receipt.png' % self.item_id
        r = self._web(self.request_owner).get(url)
        self.assertEqual((r.status_code, r.data), (200, b'png-bytes'))
        self.assertEqual(r.headers['Content-Type'], 'image/png')
        self.assertIn('private', r.headers['Cache-Control'])
        if self.users['operations_member']:        # approved items desk
            self.assertEqual(self._web(self.users['operations_member']).get(url).status_code, 200)

    def test_out_of_scope_is_refused(self):
        # Someone who may see only their own requests, and holds no item desk.
        stranger = self.users['finance_member']
        web = branding_gate.app.test_client()
        with web.session_transaction() as sess:
            sess.update({'user_id': stranger, 'mobile': 'm', 'email': 'e', 'username': 'u', 'name': 'T',
                         'roles': ['x'], 'role_code': 'x', 'perms': {'sales_request.view': 'own'},
                         'perms_loaded_at': __import__('datetime').datetime.now().isoformat()})
        branding_gate.session_permissions_are_stale, stale = (lambda: False), branding_gate.session_permissions_are_stale
        try:
            r = web.get('/uploads/items/%d/receipt.png' % self.item_id)
        finally:
            branding_gate.session_permissions_are_stale = stale
        self.assertEqual(r.status_code, 403)

    def test_unknown_folder_and_traversal(self):
        web = self._web(self.request_owner)
        self.assertEqual(web.get('/uploads/notes/secret.txt').status_code, 403)
        self.assertEqual(web.get('/uploads/../branding_gate.py').status_code, 404)
        self.assertEqual(web.get('/uploads/items/%2e%2e/%2e%2e/branding_gate.py').status_code, 404)
        self.assertEqual(web.get('/uploads/items/%d/missing.png' % self.item_id).status_code, 404)

    def test_company_documents_need_company_or_client_view(self):
        finance = self.users['finance_member']
        perms, _ = branding_gate.load_permissions(finance)
        expected = 200 if ('company.view' in perms or 'client.view' in perms) else 403
        self.assertEqual(self._web(finance).get('/uploads/companies/9/doc.pdf').status_code, expected)


if __name__ == '__main__':
    unittest.main()
