"""
My Expenses paid to suppliers (Ahmed, 2026-11-11).

The supplier must be one Finance keeps an account for: no typed names (they
reached Finance as "Unknown"), shown as the company (Royal Vision, not the
person, Mohamed Talha). Every expense carries a document before it is sent or
approved. A line paid to a supplier posts to 2101 on that supplier's own
account (21011, 21012, ...), and Finance sees what the SR owes that supplier.
Rollback-based, like test_supplier_accounts.py.
"""

import testdb  # noqa: F401  first: the test database, not the live one
import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass


class SupplierExpenseAccountsTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db=testdb.DB, charset="utf8mb4", use_unicode=True)
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
        cur.execute("INSERT INTO supplier (supplier_name, company_name, status, added_by) "
                    "VALUES ('Person T', 'Vision Co T', 'Active', 't')")
        self.supplier = cur.lastrowid
        branding_gate.assign_supplier_accounts(cur)
        cur.execute("SELECT id, client_id, company_id FROM sales_request ORDER BY id LIMIT 1")
        self.sr = cur.fetchone()['id']
        cur.execute("""INSERT INTO sales_request_items (request_id, name, qty, cost_per_item, total_cost,
                           approval_status, supplier_id, client_approval_date)
                       VALUES (%s, 'Screen', 1, 3000, 3000, 'approved', %s, '2026-11-01')""", (self.sr, self.supplier))
        cur.execute("INSERT INTO payment_methods (method_name, method_code, method_type, current_balance) "
                    "VALUES ('Sup Exp Box', 'SUP_EXP_BOX', 'cash', 0)")
        self.pm = cur.lastrowid
        cur.execute("INSERT INTO user_finance_balances (user_id, balance) VALUES (%s, 50000) "
                    "ON DUPLICATE KEY UPDATE balance = balance + 50000", (self.spender,))

    def _undo(self):
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _web(self, user_id):
        perms, role = branding_gate.load_permissions(user_id)
        web = branding_gate.app.test_client()
        with web.session_transaction() as s:
            s.update({'user_id': user_id, 'mobile': 'm', 'email': 'e', 'username': 'u', 'name': 'T',
                      'roles': [role], 'perms': perms, 'role_code': role})
        return web

    def _line(self, status='manager_approved', supplier_id=None, supplier_name='Transportation', doc=True, amount=1000):
        cur = self._cursor()
        cur.execute("""INSERT INTO user_expense_tracking (user_id, tracking_code, supplier_id, supplier_name,
                           sales_request_id, amount, description, expense_date, status)
                       VALUES (%s, CONCAT('EXP-S', FLOOR(RAND() * 1000000)), %s, %s, %s, %s, 'x', '2026-11-11', %s)""",
                    (self.spender, supplier_id, supplier_name, self.sr, amount, status))
        line = cur.lastrowid
        if doc:
            cur.execute("INSERT INTO expense_attachments (expense_id, stored_path, original_name, file_type) "
                        "VALUES (%s, '/nowhere/r.pdf', 'r.pdf', 'application/pdf')", (line,))
        return line

    def test_suppliers_number_under_2101_and_keep_their_code(self):
        cur = self._cursor()
        cur.execute("SELECT account_code FROM supplier WHERE id = %s", (self.supplier,))
        code = cur.fetchone()['account_code']
        self.assertTrue(code.startswith('2101') and len(code) > 4, code)
        cur.execute("INSERT INTO supplier (supplier_name, status, added_by) VALUES ('Next T', 'Active', 't')")
        nxt = cur.lastrowid
        branding_gate.assign_supplier_accounts(cur)
        cur.execute("SELECT id, account_code FROM supplier WHERE id IN (%s, %s)", (self.supplier, nxt))
        codes = {r['id']: r['account_code'] for r in cur.fetchall()}
        self.assertEqual(codes[self.supplier], code)
        self.assertEqual(int(codes[nxt][4:]), int(code[4:]) + 1)

    def test_a_typed_supplier_is_refused_and_the_company_is_the_name(self):
        web = self._web(self.spender)
        base = {'amount': 50, 'description': 'd', 'expense_date': '2026-11-11', 'sales_request_id': self.sr}
        r = web.post('/api/my-expenses', json=dict(base, supplier_name='Somebody'))
        self.assertEqual(r.status_code, 400, r.get_json())
        r = web.post('/api/my-expenses', json=dict(base, supplier_id=self.supplier, supplier_name='Somebody'))
        self.assertEqual(r.status_code, 200, r.get_json())
        mine = [e for e in web.get('/api/my-expenses').get_json()['expenses'] if e['id'] == r.get_json()['expense_id']][0]
        self.assertEqual((mine['supplier_name'], mine['supplier_display']), ('Vision Co T', 'Vision Co T'))
        self.assertEqual(web.post('/api/my-expenses', json=dict(base, supplier_name='Transportation')).status_code, 200)
        listed = {s['id']: s for s in web.get('/api/finance/suppliers').get_json()['suppliers']}
        self.assertEqual(listed[self.supplier]['label'], 'Vision Co T')
        self.assertTrue(all(s['label'] for s in listed.values()))

    def test_only_the_requests_own_suppliers(self):
        cur = self._cursor()
        cur.execute("INSERT INTO supplier (supplier_name, status, added_by) VALUES ('Elsewhere T', 'Active', 't')")
        elsewhere = cur.lastrowid
        web = self._web(self.spender)
        listed = [s['id'] for s in web.get('/api/finance/suppliers?sales_request_id=%d' % self.sr).get_json()['suppliers']]
        self.assertIn(self.supplier, listed)
        self.assertNotIn(elsewhere, listed)
        r = web.post('/api/my-expenses', json={'amount': 50, 'description': 'd', 'expense_date': '2026-11-11',
                                               'sales_request_id': self.sr, 'supplier_id': elsewhere})
        self.assertEqual(r.status_code, 400)
        self.assertIn('not assigned', r.get_json()['error'])

    def test_no_document_no_sending_and_no_approval(self):
        bare = self._line(status='draft', doc=False)
        r = self._web(self.spender).post('/api/my-expenses/submit')
        self.assertEqual(r.status_code, 400)
        cur = self._cursor()
        cur.execute("SELECT tracking_code FROM user_expense_tracking WHERE id = %s", (bare,))
        self.assertIn(cur.fetchone()['tracking_code'], r.get_json()['missing_documents'])
        cur.execute("SELECT id FROM finance_categories WHERE account_code = '6212'")
        transport = cur.fetchone()['id']
        cur.execute("UPDATE user_expense_tracking SET status = 'manager_approved' WHERE id = %s", (bare,))
        r = self._web(self.finance).post('/api/finance/expense-approvals/finance-approve-bulk', json={
            'payment_method_id': self.pm, 'expenses': [{'id': bare, 'amount': 1000, 'category_id': transport}]})
        self.assertEqual(r.status_code, 400)
        self.assertTrue(r.get_json()['missing_documents'])

    def test_a_supplier_line_posts_to_its_own_2101_account(self):
        line = self._line(supplier_id=self.supplier, supplier_name='Vision Co T', amount=1000)
        finance = self._web(self.finance)
        listed = [e for e in finance.get('/api/finance/expense-approvals?status=pending_finance').get_json()['expenses']
                  if e['id'] == line][0]
        self.assertEqual((listed['supplier_sr']['purchased'], listed['supplier_sr']['remaining']), (3000.0, 3000.0))
        # No category needed: the system puts it on 2101.
        r = finance.post('/api/finance/expense-approvals/finance-approve-bulk', json={
            'payment_method_id': self.pm, 'expenses': [{'id': line, 'amount': 1000}]})
        self.assertEqual(r.status_code, 200, r.get_json())
        cur = self._cursor()
        cur.execute("""SELECT fc.account_code, ft.sales_request_id FROM finance_transactions ft
                       JOIN finance_categories fc ON fc.id = ft.category_id
                       WHERE ft.supplier_id = %s AND ft.transaction_type = 'expense'""", (self.supplier,))
        self.assertEqual([(r['account_code'], r['sales_request_id']) for r in cur.fetchall()], [('2101', self.sr)])

        tree = finance.get('/api/finance/tree').get_json()
        node = branding_gate.chart_find(tree['classes'], '2101')
        mine = [k for k in node['children'] if k.get('supplier') == self.supplier][0]
        # Owed 3000 (the client-approved item), paid 1000: the account holds 2000, as the statement does.
        self.assertEqual((mine['name'], mine['credit'], mine['debit'], mine['value']), ('Vision Co T', 3000.0, 1000.0, 2000.0))
        self.assertGreaterEqual(node['debit'], sum(k['debit'] for k in node['children']))   # 2101 holds its suppliers
        self.assertTrue(tree['balanced'])
        owed = branding_gate.supplier_purchases_by_request(cur, self.supplier, self.sr)[0]
        self.assertEqual((owed['paid'], owed['remaining']), (1000.0, 2000.0))


if __name__ == '__main__':
    unittest.main()
