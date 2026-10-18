"""
Credit Inventory figures follow every stock movement.

Stock In / Stock Out from the item page moved the stock but left the credit
record's received / sold / remaining untouched, so the Credit Inventory page
showed 800 received and 800 remaining after 300 had gone out. Rollback-based.
"""

import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def close(self): pass


class CreditInventorySyncTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self.raw.cursor(MySQLdb.cursors.DictCursor))
        branding_gate.app.config['TESTING'] = True
        self._notify = branding_gate.notify_users
        branding_gate.notify_users = lambda *a, **k: 0
        cur = self._cursor()
        cur.execute("""INSERT INTO inventory_items (item_code, item_name, quantity_in_stock, minimum_stock_level,
                       is_credit_item, status) VALUES ('CRD-T9', 'Credit test 9', 800, 0, 1, 'active')""")
        self.item = cur.lastrowid
        cur.execute("""INSERT INTO inventory_credit_items (item_id, quantity_received, quantity_sold, quantity_returned,
                       quantity_remaining, agreed_cost_per_item, total_value, amount_due, status)
                       VALUES (%s, 800, 0, 0, 800, 10, 8000, 8000, 'active')""", (self.item,))
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

    def _post(self, ttype, qty, cost=0):
        perms, role = branding_gate.load_permissions(self.member)
        web = branding_gate.app.test_client()
        with web.session_transaction() as s:
            s.update({'user_id': self.member, 'mobile': 'm', 'email': 'e', 'username': 'u', 'name': 'T',
                      'roles': [role], 'perms': perms, 'role_code': role})
        r = web.post('/api/inventory/transactions/add',
                     json={'item_id': self.item, 'transaction_type': ttype, 'quantity': qty, 'unit_cost': cost})
        self.assertEqual(r.status_code, 200, r.get_json())

    def _credit(self):
        cur = self._cursor()
        cur.execute("""SELECT quantity_received r, quantity_sold s, quantity_returned t, quantity_remaining m, amount_due d
                       FROM inventory_credit_items WHERE id = %s""", (self.credit,))
        row = cur.fetchone()
        return tuple(float(row[k]) for k in ('r', 's', 't', 'm', 'd'))

    def test_stock_out_then_credit_in(self):
        self._post('stock_out', 300)
        self.assertEqual(self._credit(), (800.0, 300.0, 0.0, 500.0, 8000.0))
        self._post('credit_in', 100)                  # no cost given: the agreed cost applies
        self.assertEqual(self._credit(), (900.0, 300.0, 0.0, 600.0, 9000.0))

    def test_regular_items_are_untouched(self):
        cur = self._cursor()
        self.assertIsNone(branding_gate.sync_credit_item(cur, 999999999, 'stock_out', 5))


if __name__ == '__main__':
    unittest.main()
