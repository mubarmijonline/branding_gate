"""
Stock under a code inside one item.

"ميلجا" was two items: 500 received under code 10 and 1,200 without one.
It is one item now, and its stock splits into general and per code. A
movement may carry a code; taking out of a code or out of general cannot
overdraw it. Retired items leave the Credit Inventory list. Rollback-based.
"""

import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def close(self): pass


class LotCodesTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        self._notify = branding_gate.notify_users
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self.raw.cursor(MySQLdb.cursors.DictCursor))
        branding_gate.notify_users = lambda *a, **k: 0
        branding_gate.app.config['TESTING'] = True
        cur = self._cursor()
        cur.execute("""INSERT INTO inventory_items (item_code, item_name, quantity_in_stock, minimum_stock_level,
                       is_credit_item, status) VALUES ('LOT-T1', 'Lot test 1', 100, 0, 1, 'active')""")
        self.item = cur.lastrowid
        cur.execute("""INSERT INTO inventory_credit_items (item_id, quantity_received, quantity_remaining, status)
                       VALUES (%s, 100, 100, 'active')""", (self.item,))
        self.credit = cur.lastrowid
        cur.execute("""SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
                       WHERE r.code = 'operations_member' AND u.is_active = 1 ORDER BY u.id LIMIT 1""")
        self.member = cur.fetchone()['id']
        cur.close()

    def _undo(self):
        branding_gate.notify_users = self._notify
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

    def _move(self, web, ttype, qty, code=None):
        return web.post('/api/inventory/transactions/add', json={
            'item_id': self.item, 'transaction_type': ttype, 'quantity': qty, 'lot_code': code})

    def _split(self, web):
        return web.get('/api/inventory/items/%d/stock-by-code' % self.item).get_json()

    def test_split_and_no_overdraw(self):
        web = self._web()
        self.assertEqual(self._move(web, 'purchase', 50, ' 10 ').status_code, 200)
        split = self._split(web)
        self.assertEqual((split['total'], split['general'], split['codes']), (150.0, 100.0, [{'code': '10', 'quantity': 50.0}]))
        refused = self._move(web, 'stock_out', 60, '10')
        self.assertEqual(refused.status_code, 400)
        self.assertIn('Only 50 in code 10', refused.get_json()['error'])
        self.assertEqual(self._move(web, 'stock_out', 120).status_code, 400)       # general holds 100
        self.assertEqual(self._move(web, 'stock_out', 50, '10').status_code, 200)
        split = self._split(web)
        self.assertEqual((split['general'], split['codes']), (100.0, []))

    def test_credit_add_quantity_under_a_code(self):
        web = self._web()
        r = web.post('/api/inventory/credit-items/%d/add-quantity' % self.credit, json={'quantity': 500, 'lot_code': '10'})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(self._split(web)['codes'], [{'code': '10', 'quantity': 500.0}])
        listed = next(c for c in web.get('/api/inventory/credit-items').get_json()['credit_items'] if c['id'] == self.credit)
        self.assertEqual(listed['stock_by_code']['general'], 100.0)

    def test_retired_items_leave_the_credit_list(self):
        cur = self._cursor()
        cur.execute("UPDATE inventory_items SET status = 'discontinued' WHERE id = %s", (self.item,))
        ids = [c['id'] for c in self._web().get('/api/inventory/credit-items').get_json()['credit_items']]
        self.assertNotIn(self.credit, ids)


if __name__ == '__main__':
    unittest.main()
