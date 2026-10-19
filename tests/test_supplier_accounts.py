"""
Supplier accounts: what we owe each supplier and what we paid them.

Owed: the cost of approved SR items they supplied, plus any balance brought
forward. Paid: approved expenses carrying the supplier. Finance records a
payment from a payment method and it lands on the statement and in Finance
Management. Rollback-based.
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


class SupplierAccountsTest(unittest.TestCase):

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
        self.outsider = next(r['id'] for r in rows if r['code'] == 'operations_member')
        cur.execute("INSERT INTO supplier (supplier_name, company_name, status, added_by) VALUES ('Sup T', 'Sup Co T', 'Active', 't')")
        self.supplier = cur.lastrowid
        cur.execute("SELECT id, client_id, company_id FROM sales_request ORDER BY id LIMIT 1")
        sr = cur.fetchone()
        self.sr = sr['id']
        cur.execute("""INSERT INTO sales_request_items (request_id, name, qty, cost_per_item, total_cost, approval_status,
                           supplier_id, client_approval_date)
                       VALUES (%s, 'Truss', 2, 5000, 10000, 'approved', %s, '2026-10-02'),
                              (%s, 'Not approved', 1, 999, 999, 'pending', %s, NULL)""",
                    (self.sr, self.supplier, self.sr, self.supplier))
        cur.execute("""INSERT INTO payment_methods (method_name, method_code, method_type, current_balance)
                       VALUES ('Sup Box T', 'SUP_BOX_T', 'cash', 50000)""")
        self.pm = cur.lastrowid

    def _undo(self):
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _web(self, uid):
        perms, role = branding_gate.load_permissions(uid)
        web = branding_gate.app.test_client()
        with web.session_transaction() as s:
            s.update({'user_id': uid, 'mobile': 'm', 'email': 'e', 'username': 'u', 'name': 'T',
                      'roles': [role], 'perms': perms, 'role_code': role})
        return web

    def _balance(self):
        cur = self._cursor()
        cur.execute("SELECT current_balance FROM payment_methods WHERE id = %s", (self.pm,))
        return float(cur.fetchone()['current_balance'])

    def test_owed_paid_and_statement(self):
        finance = self._web(self.finance)
        url = '/api/finance/supplier-accounts/%d' % self.supplier
        self.assertEqual(finance.post(url + '/opening', json={'as_of': '2026-09-01', 'amount': 1500}).status_code, 200)
        # A payment needs a method, and cannot take more than the box holds.
        self.assertEqual(finance.post(url + '/payment', json={'amount': 4000}).status_code, 400)
        self.assertEqual(finance.post(url + '/payment', json={'amount': 60000, 'payment_method_id': self.pm}).status_code, 400)
        r = finance.post(url + '/payment', json={'amount': 4000, 'payment_method_id': self.pm, 'date': '2026-10-05',
                                                 'sales_request_id': self.sr, 'reference': 'CHQ 77'})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(self._balance(), 46000.0)
        cur = self._cursor()
        cur.execute("""SELECT ft.transaction_type, ft.status, ft.supplier_id, fc.category_code FROM finance_transactions ft
                       JOIN finance_categories fc ON fc.id = ft.category_id WHERE ft.id = %s""", (r.get_json()['transaction_id'],))
        self.assertEqual(cur.fetchone(), {'transaction_type': 'expense', 'status': 'approved',
                                          'supplier_id': self.supplier, 'category_code': 'SUPPLIER_PAYMENT'})

        st = finance.get(url + '/statement').get_json()
        self.assertEqual([(e['kind'], e['debit'], e['credit'], e['balance']) for e in st['entries']],
                         [('opening', 0.0, 1500.0, 1500.0), ('purchase', 0.0, 10000.0, 11500.0),
                          ('payment', 4000.0, 0.0, 7500.0)])
        self.assertEqual(st['closing'], 7500.0)
        # From a start date, earlier entries fold into the opening.
        later = finance.get(url + '/statement?start=2026-10-03').get_json()
        self.assertEqual((later['opening'], len(later['entries']), later['closing']), (11500.0, 1, 7500.0))

        row = next(r for r in finance.get('/api/finance/supplier-accounts').get_json()['rows'] if r['id'] == self.supplier)
        self.assertEqual((row['opening'], row['credit'], row['debit'], row['closing']), (1500.0, 10000.0, 4000.0, 7500.0))
        for path in ('/api/finance/supplier-accounts?format=xlsx', url + '/statement?format=xlsx'):
            self.assertEqual(finance.get(path).status_code, 200)
        self.assertEqual(finance.get('/finance/suppliers/%d' % self.supplier).status_code, 200)

    def test_outsiders_cannot_see_or_pay(self):
        web = self._web(self.outsider)
        self.assertIn(web.get('/api/finance/supplier-accounts').status_code, (302, 403))
        self.assertIn(web.post('/api/finance/supplier-accounts/%d/payment' % self.supplier,
                               json={'amount': 1, 'payment_method_id': self.pm}).status_code, (302, 403))


class FinanceNavTest(SupplierAccountsTest):
    """One bar on every Finance page."""

    def test_bar_on_every_finance_page(self):
        web = self._web(self.finance)
        for path in ('/finance', '/finance_management', '/finance/approvals', '/finance/accounts', '/invoices',
                     '/finance/suppliers', '/expense-tracking', '/finance-expense-approval'):
            r = web.get(path)
            self.assertEqual(r.status_code, 200, path)
            html = r.get_data(as_text=True)
            self.assertIn('class="fin-nav"', html, path)
            self.assertIn('Supplier Accounts', html, path)

    def test_owed_paid_and_statement(self): pass
    def test_outsiders_cannot_see_or_pay(self): pass


if __name__ == '__main__':
    unittest.main()
