"""
One row per item name.

"ميلجا" was received twice as two credit items, each holding its own stock.
A new item whose name matches an existing one -- ignoring case, spacing,
punctuation and Arabic spelling variants -- is refused with 409 and the
existing item, so the page can offer to add to its stock instead.
Rollback-based.
"""

import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def close(self): pass


class NormalizeTest(unittest.TestCase):

    def test_same_item(self):
        same = [('ميلجا', ' ميلجا '), ('مِيلْجَا', 'ميلجا'), ('أحمد', 'احمد'), ('شاشة', 'شاشه'),
                ('مستشفى', 'مستشفي'), ('Coffee  Cup', 'coffee-cup'), ('كود ٤٥٠', 'كود 450'), ('ميـــلجا', 'ميلجا')]
        for a, b in same:
            self.assertEqual(branding_gate.normalize_item_name(a), branding_gate.normalize_item_name(b), (a, b))

    def test_different_items(self):
        self.assertNotEqual(branding_gate.normalize_item_name('booth'), branding_gate.normalize_item_name('both'))
        self.assertEqual(branding_gate.normalize_item_name('  '), '')


class TwinRoutesTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self.raw.cursor(MySQLdb.cursors.DictCursor))
        branding_gate.app.config['TESTING'] = True
        cur = self._cursor()
        cur.execute("SELECT id FROM entities ORDER BY id LIMIT 2")
        self.entities = [r['id'] for r in cur.fetchall()]
        cur.execute("""INSERT INTO inventory_items (entity_id, item_code, item_name, quantity_in_stock, minimum_stock_level,
                       is_credit_item, status) VALUES (%s, 'TW-1', 'شاشة عرض', 5, 1, 0, 'active')""", (self.entities[0],))
        self.regular = cur.lastrowid
        cur.execute("""INSERT INTO inventory_items (item_code, item_name, quantity_in_stock, minimum_stock_level,
                       is_credit_item, status) VALUES ('TW-2', 'ميلجا تست', 50, 0, 1, 'active')""")
        self.credit_item = cur.lastrowid
        cur.execute("""INSERT INTO inventory_credit_items (item_id, quantity_received, quantity_remaining, status)
                       VALUES (%s, 50, 50, 'active')""", (self.credit_item,))
        self.credit = cur.lastrowid
        cur.execute("""SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
                       WHERE r.code = 'operations_member' AND u.is_active = 1 ORDER BY u.id LIMIT 1""")
        self.member = cur.fetchone()['id']
        cur.close()

    def _undo(self):
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _web(self):
        perms, role = branding_gate.load_permissions(self.member)
        web = branding_gate.app.test_client()
        with web.session_transaction() as s:
            s.update({'user_id': self.member, 'mobile': 'm', 'email': 'e', 'username': 'u', 'name': 'T',
                      'roles': [role], 'perms': perms, 'role_code': role})
        return web

    def test_regular_twin_refused_in_same_entity_only(self):
        web = self._web()
        body = {'item_name': 'شاشه  عرض', 'entity_id': self.entities[0], 'minimum_stock_level': 1, 'quantity_in_stock': 3}
        r = web.post('/api/inventory/items/add', json=body)
        self.assertEqual(r.status_code, 409, r.get_json())
        self.assertEqual(r.get_json()['duplicate']['id'], self.regular)
        if len(self.entities) > 1:
            other = web.post('/api/inventory/items/add', json=dict(body, entity_id=self.entities[1]))
            self.assertEqual(other.status_code, 200, other.get_json())

    def test_credit_twin_refused_with_its_credit_record(self):
        r = self._web().post('/api/inventory/credit-items/add',
                             json={'item_name': 'مِيلجا تست', 'quantity_received': 10})
        self.assertEqual(r.status_code, 409, r.get_json())
        twin = r.get_json()['duplicate']
        self.assertEqual((twin['id'], twin['credit_id'], twin['is_credit']), (self.credit_item, self.credit, True))

    def test_name_check_as_you_type(self):
        web = self._web()
        hit = web.get('/api/inventory/items/name-check', query_string={'name': 'ميلجا تست', 'credit': '1'}).get_json()
        self.assertEqual(hit['duplicate']['item_code'], 'TW-2')
        miss = web.get('/api/inventory/items/name-check', query_string={'name': 'شيء جديد', 'credit': '1'}).get_json()
        self.assertIsNone(miss['duplicate'])
        self.assertIsNone(web.get('/api/inventory/items/name-check', query_string={
            'name': 'ميلجا تست', 'credit': '1', 'exclude_id': self.credit_item}).get_json()['duplicate'])


if __name__ == '__main__':
    unittest.main()
