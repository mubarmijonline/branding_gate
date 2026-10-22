"""
Finance approving My Expenses lines.

Approve All wrote payment method id 1, which does not exist, so the foreign key
refused every approval; and a line without a category was silently skipped.
Now Finance picks the method (default: the first active cash one) and every
line must carry a category or nothing is approved. Rollback-based.
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


class ExpenseFinanceApprovalTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self.raw.cursor(MySQLdb.cursors.DictCursor))
        branding_gate.app.config['TESTING'] = True
        cur = self._cursor()
        cur.execute("""SELECT u.id, r.code FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
                       WHERE u.is_active = 1 AND r.code IN ('finance_manager', 'operations_member') ORDER BY u.id""")
        rows = cur.fetchall()
        self.finance = next(r['id'] for r in rows if r['code'] == 'finance_manager')
        self.spender = next(r['id'] for r in rows if r['code'] == 'operations_member')
        cur.execute("INSERT INTO payment_methods (method_name, method_code, method_type, current_balance) "
                    "VALUES ('Test Box 4x', 'TEST_BOX_4X', 'cash', 0)")
        self.pm = cur.lastrowid
        self.lines = []
        for n in range(2):
            cur.execute("""INSERT INTO user_expense_tracking (user_id, tracking_code, supplier_name, amount,
                           description, expense_date, status) VALUES (%s, %s, 'Transportation', 100, 'Taxi',
                           '2026-10-18', 'manager_approved')""", (self.spender, 'EXP-T4-%d' % n))
            self.lines.append(cur.lastrowid)
        cur.close()

    def _undo(self):
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def account(self, code):
        cur = self._cursor()
        cur.execute("SELECT id FROM finance_categories WHERE account_code = %s", (code,))
        return cur.fetchone()['id']

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _web(self):
        perms, role = branding_gate.load_permissions(self.finance)
        web = branding_gate.app.test_client()
        with web.session_transaction() as s:
            s.update({'user_id': self.finance, 'mobile': 'm', 'email': 'e', 'username': 'u', 'name': 'T',
                      'roles': [role], 'perms': perms, 'role_code': role})
        return web

    def test_default_method_is_an_existing_active_one(self):
        cur = self._cursor()
        pm, error = branding_gate.expense_payment_method(cur)
        self.assertIsNone(error)
        cur.execute("SELECT is_active FROM payment_methods WHERE id = %s", (pm,))
        self.assertEqual(cur.fetchone()['is_active'], 1)
        self.assertEqual(branding_gate.expense_payment_method(cur, 999999999)[1], 'Payment method not found or inactive')

    def test_a_missing_category_refuses_the_whole_batch(self):
        r = self._web().post('/api/finance/expense-approvals/finance-approve-bulk', json={
            'payment_method_id': self.pm,
            'expenses': [{'id': self.lines[0], 'amount': 100, 'category_id': self.account('6212')},
                         {'id': self.lines[1], 'amount': 100}]})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()['missing_category'], [str(self.lines[1])])
        cur = self._cursor()
        cur.execute("SELECT COUNT(*) AS n FROM user_expense_tracking WHERE id IN (%s, %s) AND status = 'approved'",
                    tuple(self.lines))
        self.assertEqual(cur.fetchone()['n'], 0)

    def test_approve_all_records_on_the_chosen_method(self):
        r = self._web().post('/api/finance/expense-approvals/finance-approve-bulk', json={
            'payment_method_id': self.pm,
            'expenses': [{'id': i, 'amount': 100, 'category_id': self.account('62'), 'subcategory_id': self.account('6212')}
                         for i in self.lines]})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()['approved_count'], 2)
        cur = self._cursor()
        cur.execute("SELECT COUNT(*) AS n FROM finance_transactions WHERE payment_method_id = %s", (self.pm,))
        self.assertEqual(cur.fetchone()['n'], 4)     # income + expense per line
        cur.execute("SELECT COUNT(*) AS n FROM user_expense_tracking WHERE id IN (%s, %s) AND status = 'approved'",
                    tuple(self.lines))
        self.assertEqual(cur.fetchone()['n'], 2)


if __name__ == '__main__':
    unittest.main()
