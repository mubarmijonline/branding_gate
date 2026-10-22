"""
Finance categories, managed from the Categories tab and the Finance Tree.

Finance adds categories and sub-categories (system ones take subs too),
renames non-system ones, and cannot create a second category with the same
name under the same parent. Rollback-based.
"""

import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass


class FinanceCategoriesTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self.raw.cursor(MySQLdb.cursors.DictCursor))
        branding_gate.app.config['TESTING'] = True
        cur = self.raw.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("""SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
                       WHERE u.is_active = 1 AND r.code = 'finance_manager' ORDER BY u.id LIMIT 1""")
        uid = cur.fetchone()['id']
        perms, role = branding_gate.load_permissions(uid)
        self.web = branding_gate.app.test_client()
        with self.web.session_transaction() as s:
            s.update({'user_id': uid, 'mobile': 'm', 'email': 'e', 'username': 'u', 'name': 'T',
                      'roles': [role], 'perms': perms, 'role_code': role})

    def _undo(self):
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _add(self, name, **extra):
        return self.web.post('/api/finance/categories', json=dict(category_name=name, category_type='expense', **extra))

    def test_add_rename_and_no_duplicates(self):
        r = self._add('Cat Test Rent')
        self.assertEqual(r.status_code, 200, r.get_json())
        root = r.get_json()['id']
        self.assertEqual(self._add('  cat test RENT ').status_code, 409)              # same name, same level
        sub = self._add('Cat Test Office', parent_id=root).get_json()['id']
        self.assertEqual(self._add('cat test office', parent_id=root).status_code, 409)
        self.assertEqual(self._add('Cat Test Office').status_code, 200)               # another level is fine
        # Rename: refused onto a sibling's name, accepted otherwise.
        self.assertEqual(self._add('Cat Test Warehouse', parent_id=root).status_code, 200)
        self.assertEqual(self.web.put('/api/finance/categories/%d' % sub, json={'category_name': 'Cat Test Warehouse'}).status_code, 409)
        self.assertEqual(self.web.put('/api/finance/categories/%d' % sub, json={'category_name': 'Cat Test HQ'}).status_code, 200)
        tree = self.web.get('/api/finance/tree').get_json()
        node = next(c for c in tree['expense']['categories'] if c['id'] == root)
        self.assertEqual(sorted(c['name'] for c in node['children']), ['Cat Test HQ', 'Cat Test Warehouse'])
        self.assertFalse(node['is_system'])
        # Delete takes the subs with it, and the name is free again.
        self.assertEqual(self.web.delete('/api/finance/categories/%d' % root).status_code, 200)
        self.assertEqual(self._add('Cat Test Rent').status_code, 200)

    def test_system_categories_take_subs_but_keep_their_name(self):
        tree = self.web.get('/api/finance/tree').get_json()
        supplier_payments = next(c for c in tree['expense']['categories'] if c['id'] == 10)
        self.assertTrue(supplier_payments['is_system'])
        self.assertEqual(self._add('Cat Test Printing', parent_id=10).status_code, 200)
        self.assertEqual(self.web.put('/api/finance/categories/10', json={'category_name': 'Renamed'}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
