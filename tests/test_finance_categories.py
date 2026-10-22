"""
The chart of accounts (Finance Tree), its editing and its postings.

The chart is seeded from finance_chart.py with Finance's codes; the system's own
rows sit on their mapped accounts; Finance adds accounts under any node (next
free code, or a valid one of its own), renames and re-codes non-system ones;
names are unique under a parent; a transaction posts to one leaf account and
rolls up through its group and class. Rollback-based.
"""

import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate
import finance_chart


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass


class ChartUnitTest(unittest.TestCase):

    def test_codes(self):
        codes = {c for c, _ in finance_chart.CHART}
        self.assertEqual(len(codes), len(finance_chart.CHART))                  # no code twice (2201, not 2101)
        self.assertEqual(finance_chart.parent_code('111003', codes), '1110')
        self.assertEqual(finance_chart.parent_code('3101', codes), '3')
        self.assertIsNone(finance_chart.parent_code('6', codes))
        self.assertEqual(finance_chart.next_code('62', ['6201', '6214']), '6215')
        self.assertEqual(finance_chart.next_code('1110', []), '111001')
        self.assertEqual(finance_chart.next_code('6', ['61', '64']), '65')


class FinanceCategoriesTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self.raw.cursor(MySQLdb.cursors.DictCursor))
        branding_gate.app.config['TESTING'] = True
        cur = self._cursor()
        cur.execute("""SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
                       WHERE u.is_active = 1 AND r.code = 'finance_manager' ORDER BY u.id LIMIT 1""")
        uid = cur.fetchone()['id']
        perms, role = branding_gate.load_permissions(uid)
        self.web = branding_gate.app.test_client()
        with self.web.session_transaction() as s:
            s.update({'user_id': uid, 'mobile': 'm', 'email': 'e', 'username': 'u', 'name': 'T',
                      'roles': [role], 'perms': perms, 'role_code': role})
        cur.execute("""INSERT INTO payment_methods (method_name, method_code, method_type, current_balance)
                       VALUES ('Chart Box T', 'CHART_BOX_T', 'cash', 100000)""")
        self.pm = cur.lastrowid
        self.ids = {r['account_code']: r['id'] for r in self._rows("SELECT id, account_code FROM finance_categories WHERE is_active = 1")}

    def _undo(self):
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _rows(self, sql, params=()):
        cur = self._cursor()
        cur.execute(sql, params)
        return cur.fetchall()

    def _add(self, name, parent_code, **extra):
        return self.web.post('/api/finance/categories',
                             json=dict(category_name=name, parent_id=self.ids[parent_code], **extra))

    def _tree(self, **args):
        return self.web.get('/api/finance/tree', query_string=args).get_json()['classes']

    def test_seeded_with_codes_and_system_rows_on_their_accounts(self):
        self.assertEqual(len([c for c, _ in finance_chart.CHART if c in self.ids]), len(finance_chart.CHART))
        for row_id, code in finance_chart.SYSTEM_IDS.items():
            self.assertEqual(self.ids[code], row_id, code)
        classes = self._tree()
        self.assertEqual([c['code'] for c in classes], ['1', '2', '3', '4', '5', '6'])
        self.assertEqual(self._rows("SELECT COUNT(*) n FROM finance_categories WHERE is_active = 1 AND account_code IS NULL")[0]['n'], 0)

    def test_add_recode_rename_and_no_duplicates(self):
        r = self._add('Chart T Rent Store', '62')
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()['account_code'], '6215')                  # next after 6214
        acc = r.get_json()['id']
        self.assertEqual(self._add('  chart t RENT store ', '62').status_code, 409)
        self.assertEqual(self._add('Chart T Bad', '62', account_code='6101').status_code, 400)   # not under 62
        self.assertEqual(self._add('Chart T Bad', '62', account_code='6201').status_code, 400)   # taken
        sub = self._add('Chart T Branch', '62', account_code='6230').get_json()
        self.assertEqual(sub['account_code'], '6230')
        put = self.web.put('/api/finance/categories/%d' % acc, json={'category_name': 'Chart T Warehouse', 'account_code': '6231'})
        self.assertEqual(put.status_code, 200, put.get_json())
        self.assertEqual(self.web.put('/api/finance/categories/%d' % acc, json={'category_name': 'Chart T Branch'}).status_code, 409)
        node = branding_gate.chart_find(self._tree(), '6231')
        self.assertEqual(node['name'], 'Chart T Warehouse')
        # System accounts keep their name; deleting a group takes its accounts.
        self.assertEqual(self.web.put('/api/finance/categories/10', json={'category_name': 'Renamed'}).status_code, 400)
        self.assertEqual(self._add('Chart T Printing', '2101').status_code, 200)          # still takes sub-accounts
        self.assertEqual(self.web.delete('/api/finance/categories/%d' % acc).status_code, 200)
        self.assertEqual(self.web.delete('/api/finance/categories/%d' % self.ids['11']).status_code, 400)   # holds 1101, 1103...
        self.assertIsNone(branding_gate.chart_find(self._tree(), '6231'))

    def test_posting_goes_to_the_leaf_and_rolls_up(self):
        picker = self.web.get('/api/finance/categories').get_json()['categories']
        g62 = next(g for g in picker if g['account_code'] == '62')
        self.assertIn('6212', [s['account_code'] for s in g62['subcategories']])
        g11 = next(g for g in picker if g['account_code'] == '11')
        self.assertIn('111003', [s['account_code'] for s in g11['subcategories']])        # sub-accounts listed too
        self.assertIn('3101', [g['account_code'] for g in picker])                          # a class's own account
        self.assertEqual({g['class_code'] for g in self.web.get('/api/finance/categories?type=expense').get_json()['categories']},
                         {'5', '6'})
        post = lambda **kw: self.web.post('/api/finance/transactions', json=dict(
            transaction_type='expense', amount=300, payment_method_id=self.pm, transaction_date='2026-10-20', **kw))
        self.assertEqual(post(category_id=self.ids['62']).status_code, 400)                 # a group with accounts
        r = post(category_id=self.ids['62'], subcategory_id=self.ids['6212'])
        self.assertEqual(r.status_code, 200, r.get_json())
        row = self._rows("SELECT category_id, subcategory_id FROM finance_transactions WHERE id = %s",
                         (r.get_json()['id'],))[0]
        self.assertEqual((row['category_id'], row['subcategory_id']), (self.ids['6212'], None))
        income = self.web.post('/api/finance/transactions', json=dict(
            transaction_type='income', amount=5000, payment_method_id=self.pm, transaction_date='2026-10-20',
            category_id=self.ids['3101']))
        self.assertEqual(income.status_code, 200, income.get_json())
        self._cursor().execute("UPDATE finance_transactions SET status = 'approved' WHERE id IN (%s, %s)",
                               (r.get_json()['id'], income.get_json()['id']))
        tree = self._tree(start_date='2026-10-20', end_date='2026-10-20')          # the test's own day
        find = lambda code: branding_gate.chart_find(tree, code)
        self.assertEqual((find('6212')['value'], find('62')['value'], find('6')['value']), (300.0, 300.0, 300.0))
        self.assertEqual(find('3101')['value'], 5000.0)                                    # equity grows with money in
        self.assertNotIn('live', find('1101'))
        box = next(k for k in find('1101')['children'] if k['id'] == 'pm-%d' % self.pm)          # its payment method
        self.assertEqual((box['money_in'], box['money_out'], box['code'][:4]), (5000.0, 300.0, '1101'))
        self.assertFalse(any(k['id'] == 'pm-%d' % self.pm for k in find('1102')['children']))   # cash, not bank
        self.assertEqual(find('11')['money_in'], 0.0)                                          # not counted twice
        listed = self.web.get('/api/finance/transactions?status=approved&category_ids=%d' % self.ids['62']).get_json()
        self.assertEqual([t['amount'] for t in listed['transactions'] if t['id'] == r.get_json()['id']], [300.0])

    def test_transfer_between_payment_methods(self):
        cur = self._cursor()
        cur.execute("""INSERT INTO payment_methods (method_name, method_code, method_type, current_balance, bank_name, account_number)
                       VALUES ('Chart Bank T', 'CHART_BANK_T', 'bank', 0, 'CIB', '1')""")
        bank = cur.lastrowid
        balance = lambda pm: (cur.execute("SELECT current_balance FROM payment_methods WHERE id = %s", (pm,)),
                              float(cur.fetchone()['current_balance']))[1]
        stats_before = self.web.get('/api/finance/statistics').get_json()
        move = lambda **kw: self.web.post('/api/finance/payment-methods/transfer', json=dict(date='2026-10-20', **kw))
        self.assertEqual(move(from_id=self.pm, to_id=self.pm, amount=10).status_code, 400)          # same method
        self.assertEqual(move(from_id=self.pm, to_id=bank, amount=999999).status_code, 400)         # more than it holds
        r = move(from_id=self.pm, to_id=bank, amount=1000, reference='DEP 1')
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual((balance(self.pm), balance(bank)), (99000.0, 1000.0))
        tree = self._tree()
        box = next(k for k in branding_gate.chart_find(tree, '1101')['children'] if k['id'] == 'pm-%d' % self.pm)
        bnk = next(k for k in branding_gate.chart_find(tree, '1102')['children'] if k['id'] == 'pm-%d' % bank)
        self.assertEqual((box['money_out'], bnk['money_in']), (1000.0, 1000.0))
        stats = self.web.get('/api/finance/statistics').get_json()
        # A transfer is neither income nor expense.
        self.assertEqual((stats['total_income'], stats['total_expense']), (stats_before['total_income'], stats_before['total_expense']))

    def test_opening_balance_is_capital_and_the_balance_sheet_balances(self):
        before = self.web.get('/api/finance/balance-sheet').get_json()
        r = self.web.post('/api/finance/payment-methods', json={'method_name': 'Chart Opening Bank T', 'method_type': 'bank',
                                                              'bank_name': 'CIB', 'account_number': '77', 'opening_balance': 40000})
        self.assertEqual(r.status_code, 200, r.get_json())
        pm = r.get_json()['id']
        adj = self.web.post('/api/finance/payment-methods/%d/set-balance' % pm, json={'balance': 45000, 'reason': 'Owner deposit'})
        self.assertEqual(adj.status_code, 200, adj.get_json())
        rows = self._rows("""SELECT ft.transaction_type, ft.amount, fc.account_code FROM finance_transactions ft
                             JOIN finance_categories fc ON fc.id = ft.category_id WHERE ft.payment_method_id = %s ORDER BY ft.id""", (pm,))
        self.assertEqual([(x['transaction_type'], float(x['amount']), x['account_code']) for x in rows],
                         [('income', 40000.0, '3101'), ('income', 5000.0, '3101')])
        self.assertEqual(float(self._rows("SELECT current_balance FROM payment_methods WHERE id = %s", (pm,))[0]['current_balance']), 45000.0)
        after = self.web.get('/api/finance/balance-sheet').get_json()
        self.assertEqual(round(after['assets']['total'] - before['assets']['total'], 2), 45000.0)
        self.assertEqual(round(after['equity']['capital'] - before['equity']['capital'], 2), 45000.0)
        self.assertEqual(after['equity']['current_period_net'], before['equity']['current_period_net'])   # not income
        self.assertEqual(round(after['total_liabilities_and_equity'] - before['total_liabilities_and_equity'], 2), 45000.0)

    def test_income_statement_counts_posted_invoices_on_sales(self):
        cur = self._cursor()
        cur.execute("SELECT id, client_id, company_id FROM sales_request ORDER BY id LIMIT 1")
        sr = cur.fetchone()
        cur.execute("""INSERT INTO client_invoice (kind, invoice_number, sales_request_id, company_id, client_id, invoice_date,
                           billing_month, subtotal, vat_total, total, status, created_by)
                       VALUES ('invoice', 99901, %s, %s, %s, '2026-10-20', '2026-10', 1000, 140, 1130, 'posted', 1)""",
                    (sr['id'], sr['company_id'], sr['client_id']))
        got = self.web.get('/api/finance/income-statement?period=custom&start_date=2026-10-01&end_date=2026-10-31').get_json()
        sales = next(g for g in got['income']['categories'] if g['name'].startswith('41 '))
        self.assertEqual(sales['total'], 1000.0)
        # The tree counts only approved finance transactions: no invoice, no SR supplier cost.
        tree = self._tree(start_date='2026-10-01')
        self.assertEqual(branding_gate.chart_find(tree, '4101')['value'], 0.0)
        cur.execute("SELECT COALESCE(SUM(amount), 0) s FROM finance_transactions WHERE status = 'approved' AND category_id = 10")
        self.assertEqual(branding_gate.chart_find(self._tree(), '2101')['money_out'], float(cur.fetchone()['s']))


if __name__ == '__main__':
    unittest.main()
