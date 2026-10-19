"""
Client invoices, end to end.

The account manager drafts from a Sales Request and sends it to Finance;
Finance posts it (numbering it, putting it on the client's account) or
returns it. The arithmetic must reproduce Finance's sample, invoice 2452:
157,600 + VAT 22,064 - 1% profits tax 1,576 = 178,088. Rollback-based.
"""

import unittest
from decimal import Decimal

import MySQLdb
import MySQLdb.cursors

import branding_gate
import invoicing


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass


class ArithmeticTest(unittest.TestCase):

    def test_sample_2452(self):
        r = invoicing.compute_invoice([{'qty': 1, 'unit_price': 105600}, {'qty': 1, 'unit_price': 52000}])
        self.assertEqual((r['subtotal'], r['vat_total'], r['profit_tax_total'], r['total']),
                         (Decimal('157600.00'), Decimal('22064.00'), Decimal('1576.00'), Decimal('178088.00')))
        self.assertEqual(r['lines'][0]['line_total'], Decimal('120384.00'))

    def test_discount_and_no_withholding(self):
        r = invoicing.compute_invoice([{'qty': 2, 'unit_price': 100, 'cash_discount': 50}], apply_profit_tax=False)
        self.assertEqual((r['subtotal'], r['vat_total'], r['total']), (Decimal('150.00'), Decimal('21.00'), Decimal('171.00')))

    def test_refuses_negatives(self):
        with self.assertRaises(ValueError):
            invoicing.compute_line(1, 100, 150)


class InvoiceFlowTest(unittest.TestCase):

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
        cur.execute("""SELECT u.id, r.code FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
                       WHERE u.is_active = 1 AND r.code IN ('finance_manager', 'account_team_leader', 'operations_member')
                       ORDER BY u.id""")
        rows = cur.fetchall()
        self.finance = next(r['id'] for r in rows if r['code'] == 'finance_manager')
        self.account = next(r['id'] for r in rows if r['code'] == 'account_team_leader')
        self.outsider = next(r['id'] for r in rows if r['code'] == 'operations_member')
        cur.execute("SELECT id FROM company ORDER BY id LIMIT 1")
        self.company = cur.fetchone()['id']
        cur.execute("""INSERT INTO client (client_name, parent_company_id, email_address, mobile_number, added_by)
                       VALUES ('Inv Client T', %s, 'c@x', '0', 't')""", (self.company,))
        self.client_id = cur.lastrowid
        cur.execute("""INSERT INTO sales_request (client_id, company_id, title, created_by, start_date, status, owner_user_id)
                       VALUES (%s, %s, 'Invoice test SR', 't', '2026-10-01', 'submitted', %s)""",
                    (self.client_id, self.company, self.account))
        self.sr = cur.lastrowid
        cur.execute("""INSERT INTO sales_request_items (request_id, name, qty, total_sell, approval_status)
                       VALUES (%s, 'LED Screen', 1, 105600, 'approved'), (%s, 'stage', 1, 52000, 'approved'),
                              (%s, 'not approved', 1, 999, 'pending')""", (self.sr, self.sr, self.sr))
        cur.execute("DELETE FROM invoice_catalog WHERE code IN (9001, 9002)")
        cur.execute("""INSERT INTO invoice_catalog (code, name_ar, name_en) VALUES
                       (9001, 'شاشات تست', 'LED Screen'), (9002, 'استيدج تست', 'stage')""")
        cur.close()

    def _undo(self):
        branding_gate.notify_users = self._notify
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

    def _draft(self, web, lines=None):
        prefill = web.get('/api/invoices/from-request/%d' % self.sr).get_json()
        lines = lines or [{'item_code': l['item_code'], 'qty': l['qty'], 'unit_price': l['unit_price'],
                           'sales_request_item_id': l['sales_request_item_id']} for l in prefill['lines']]
        r = web.post('/api/invoices', json={'sales_request_id': self.sr, 'invoice_date': '2026-01-18',
                                            'billing_month': '2026-01', 'lines': lines})
        self.assertEqual(r.status_code, 200, r.get_json())
        return r.get_json()['id'], prefill

    def test_prefill_takes_approved_items_and_guesses_codes(self):
        _, prefill = self._draft(self._web(self.account))
        codes = sorted((l['description'], l['item_code']) for l in prefill['lines'])
        self.assertEqual(codes, [('LED Screen', 9001), ('stage', 9002)])

    def test_draft_submit_post_and_the_statement(self):
        author, finance = self._web(self.account), self._web(self.finance)
        inv_id, _ = self._draft(author)
        got = author.get('/api/invoices/%d' % inv_id).get_json()['invoice']
        self.assertEqual((got['total'], got['status']), (178088.0, 'draft'))
        self.assertEqual(finance.post('/api/invoices/%d/post' % inv_id).status_code, 400)   # not sent yet
        self.assertEqual(author.post('/api/invoices/%d/submit' % inv_id).status_code, 200)
        self.assertEqual(author.post('/api/invoices/%d/post' % inv_id).status_code, 403)    # author cannot post
        r = finance.post('/api/invoices/%d/post' % inv_id, json={'invoice_number': 2452})
        self.assertEqual(r.status_code, 200, r.get_json())
        # Locked once posted.
        locked = author.put('/api/invoices/%d' % inv_id, json={'invoice_date': '2026-01-18', 'lines': [{'qty': 1, 'unit_price': 1}]})
        self.assertEqual(locked.status_code, 400)
        # The number cannot be used twice.
        second, _ = self._draft(author)
        author.post('/api/invoices/%d/submit' % second)
        self.assertEqual(finance.post('/api/invoices/%d/post' % second, json={'invoice_number': 2452}).status_code, 400)
        # On the client's account.
        st = finance.get('/api/finance/accounts/statement?client_id=%d' % self.client_id).get_json()
        self.assertEqual((st['debit'], st['closing']), (178088.0, 178088.0))
        later = finance.get('/api/finance/accounts/statement?client_id=%d&start=2026-02-01' % self.client_id).get_json()
        self.assertEqual((later['opening'], later['entries']), (178088.0, []))
        acc = finance.get('/api/finance/accounts?client_id=%d' % self.client_id).get_json()['clients'][0]
        self.assertEqual((acc['invoiced'], acc['balance_due']), (178088.0, 178088.0))

    def test_return_needs_a_reason_and_goes_back_to_the_author(self):
        author, finance = self._web(self.account), self._web(self.finance)
        inv_id, _ = self._draft(author)
        author.post('/api/invoices/%d/submit' % inv_id)
        self.assertEqual(finance.post('/api/invoices/%d/return' % inv_id, json={'reason': ''}).status_code, 400)
        self.assertEqual(finance.post('/api/invoices/%d/return' % inv_id, json={'reason': 'Wrong month'}).status_code, 200)
        got = author.get('/api/invoices/%d' % inv_id).get_json()['invoice']
        self.assertEqual((got['status'], got['return_reason'], got['can_submit']), ('returned', 'Wrong month', True))

    def test_posting_needs_every_code_and_codes_must_exist(self):
        author, finance = self._web(self.account), self._web(self.finance)
        bad = author.post('/api/invoices', json={'sales_request_id': self.sr, 'invoice_date': '2026-01-18',
                                                 'lines': [{'item_code': '77777', 'qty': 1, 'unit_price': 5}]})
        self.assertEqual(bad.status_code, 400)
        inv_id, _ = self._draft(author, lines=[{'qty': 1, 'unit_price': 100, 'description': 'no code yet'}])
        author.post('/api/invoices/%d/submit' % inv_id)
        self.assertEqual(finance.post('/api/invoices/%d/post' % inv_id).status_code, 400)

    def test_outsiders_see_nothing(self):
        inv_id, _ = self._draft(self._web(self.account))
        outsider = self._web(self.outsider)
        self.assertEqual(outsider.get('/api/invoices').status_code, 403)
        self.assertEqual(outsider.get('/api/invoices/%d' % inv_id).status_code, 403)


if __name__ == '__main__':
    unittest.main()


class InvoicePaymentTest(InvoiceFlowTest):
    """A payment recorded against a posted invoice shows on it and on the statement."""

    def test_record_payment_against_posted_invoice(self):
        author, finance = self._web(self.account), self._web(self.finance)
        inv_id, _ = self._draft(author)
        author.post('/api/invoices/%d/submit' % inv_id)
        finance.post('/api/invoices/%d/post' % inv_id, json={'invoice_number': 98001})
        cur = self._cursor()
        cur.execute("SELECT id FROM payment_methods WHERE is_active = 1 ORDER BY id LIMIT 1")
        pm = cur.fetchone()['id']
        cur.execute("""INSERT INTO finance_transactions (transaction_code, transaction_type, amount, payment_method_id,
                       category_id, client_id, sales_request_id, reference_number, transaction_date, status, added_by)
                       VALUES ('FT-T98001', 'income', 78088, %s, 1, %s, %s, 'Invoice 98001', '2026-01-20', 'approved', 't')""",
                    (pm, self.client_id, self.sr))
        got = finance.get('/api/invoices/%d' % inv_id).get_json()['invoice']
        self.assertEqual((got['paid'], len(got['payments']), got['can_record_payment']), (78088.0, 1, True))
        st = finance.get('/api/finance/accounts/statement?client_id=%d' % self.client_id).get_json()
        self.assertEqual((st['debit'], st['credit'], st['closing']), (178088.0, 78088.0, 100000.0))
