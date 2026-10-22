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
        cur.execute("""INSERT INTO payment_methods (method_name, method_code, method_type, current_balance)
                       VALUES ('Inv Box T', 'INV_BOX_T', 'cash', 1000000)""")
        self.pm = cur.lastrowid
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

    def test_prefill_takes_approved_items_coded_by_their_id(self):
        _, prefill = self._draft(self._web(self.account))
        self.assertEqual(sorted(l['description'] for l in prefill['lines']), ['LED Screen', 'stage'])
        self.assertTrue(all(l['item_code'] == l['sales_request_item_id'] for l in prefill['lines']))

    def test_draft_submit_post_and_the_statement(self):
        author, finance = self._web(self.account), self._web(self.finance)
        inv_id, _ = self._draft(author)
        got = author.get('/api/invoices/%d' % inv_id).get_json()['invoice']
        self.assertEqual((got['total'], got['status']), (178088.0, 'draft'))
        self.assertEqual(finance.post('/api/invoices/%d/post' % inv_id, json={'payment_method_id': self.pm}).status_code, 400)   # not sent yet
        self.assertEqual(author.post('/api/invoices/%d/submit' % inv_id).status_code, 200)
        self.assertEqual(author.post('/api/invoices/%d/post' % inv_id, json={'payment_method_id': self.pm}).status_code, 403)    # author cannot post
        r = finance.post('/api/invoices/%d/post' % inv_id, json={'invoice_number': 2452, 'payment_method_id': self.pm, 'amount': 0})
        self.assertEqual(r.status_code, 200, r.get_json())
        # Locked once posted.
        locked = author.put('/api/invoices/%d' % inv_id, json={'invoice_date': '2026-01-18', 'lines': [{'qty': 1, 'unit_price': 1}]})
        self.assertEqual(locked.status_code, 400)
        # The number cannot be used twice.
        second, _ = self._draft(author)
        author.post('/api/invoices/%d/submit' % second)
        self.assertEqual(finance.post('/api/invoices/%d/post' % second, json={'invoice_number': 2452, 'payment_method_id': self.pm, 'amount': 0}).status_code, 400)
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

    def test_lines_come_from_the_request_only(self):
        author = self._web(self.account)
        prefill = author.get('/api/invoices/from-request/%d' % self.sr).get_json()
        sri = prefill['lines'][0]['sales_request_item_id']
        typed = author.post('/api/invoices', json={'sales_request_id': self.sr, 'invoice_date': '2026-01-18',
                                                   'lines': [{'qty': 1, 'unit_price': 5, 'description': 'typed in'}]})
        self.assertEqual(typed.status_code, 400)
        twice = author.post('/api/invoices', json={'sales_request_id': self.sr, 'invoice_date': '2026-01-18',
                                                   'lines': [{'sales_request_item_id': sri, 'qty': 1, 'unit_price': 5}] * 2})
        self.assertEqual(twice.status_code, 400)
        cur = self._cursor()
        cur.execute("SELECT id FROM sales_request_items WHERE request_id = %s AND approval_status = 'pending'", (self.sr,))
        pending = cur.fetchone()['id']
        unapproved = author.post('/api/invoices', json={'sales_request_id': self.sr, 'invoice_date': '2026-01-18',
                                                        'lines': [{'sales_request_item_id': pending, 'qty': 1, 'unit_price': 5}]})
        self.assertEqual(unapproved.status_code, 400)
        # The name is the request's, whatever was sent.
        inv_id, _ = self._draft(author, lines=[{'sales_request_item_id': sri, 'qty': 1, 'unit_price': 5,
                                               'description': 'renamed'}])
        line = author.get('/api/invoices/%d' % inv_id).get_json()
        self.assertEqual(line['lines'][0]['description'], 'LED Screen')

    def test_serial_from_the_start_and_released_on_cancel(self):
        author = self._web(self.account)
        cur = self._cursor()
        cur.execute("SELECT COALESCE(MAX(invoice_number), 0) AS n FROM client_invoice")
        top = cur.fetchone()['n']
        first, _ = self._draft(author)
        got = author.get('/api/invoices/%d' % first).get_json()['invoice']
        self.assertEqual(got['invoice_number'], top + 1)
        self.assertEqual(author.post('/api/invoices/%d/cancel' % first).status_code, 200)
        second, _ = self._draft(author)
        self.assertEqual(author.get('/api/invoices/%d' % second).get_json()['invoice']['invoice_number'], top + 1)

    def test_line_code_is_the_item_id_whatever_is_sent(self):
        author, finance = self._web(self.account), self._web(self.finance)
        prefill = author.get('/api/invoices/from-request/%d' % self.sr).get_json()
        sri = prefill['lines'][0]['sales_request_item_id']
        inv_id, _ = self._draft(author, lines=[{'sales_request_item_id': sri, 'item_code': '77777', 'qty': 1, 'unit_price': 100}])
        self.assertEqual(author.get('/api/invoices/%d' % inv_id).get_json()['lines'][0]['item_code'], sri)
        author.post('/api/invoices/%d/submit' % inv_id)
        self.assertEqual(finance.post('/api/invoices/%d/post' % inv_id, json={'invoice_number': 98100, 'payment_method_id': self.pm, 'amount': 0}).status_code, 200)

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
        finance.post('/api/invoices/%d/post' % inv_id, json={'invoice_number': 98001, 'payment_method_id': self.pm, 'amount': 0})
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


class StatementLayoutTest(InvoiceFlowTest):
    """George's statement: opening balance, job code, invoice number, cash or bank collections, combined balances."""

    def test_statement_and_combined_balances(self):
        author, finance = self._web(self.account), self._web(self.finance)
        self.assertEqual(finance.post('/api/finance/accounts/opening', json={
            'client_id': self.client_id, 'as_of': '2024-12-31', 'amount': 1000, 'note': 'balance 2025'}).status_code, 200)
        inv_id, _ = self._draft(author)
        author.post('/api/invoices/%d/submit' % inv_id)
        finance.post('/api/invoices/%d/post' % inv_id, json={'invoice_number': 98002, 'payment_method_id': self.pm, 'amount': 0})
        cur = self._cursor()
        cur.execute("""INSERT INTO payment_methods (method_name, method_code, method_type, bank_name, account_number)
                       VALUES ('Bank T', 'BANK_T_98', 'bank', 'CIB', '1')""")
        bank = cur.lastrowid
        cur.execute("""INSERT INTO finance_transactions (transaction_code, transaction_type, amount, payment_method_id,
                       category_id, client_id, sales_request_id, reference_number, transaction_date, status, added_by)
                       VALUES ('FT-T98002', 'income', 20000, %s, 1, %s, %s, 'Invoice 98002', '2026-01-25', 'approved', 't')""",
                    (bank, self.client_id, self.sr))
        st = finance.get('/api/finance/accounts/statement?client_id=%d' % self.client_id).get_json()
        kinds = [(e['kind'], e['label'], e['invoice_number'], e['sales_request_id']) for e in st['entries']]
        self.assertEqual(kinds, [('opening', 'Balance brought forward', None, None),
                                 ('invoice', 'Invoice 98002', 98002, self.sr),
                                 ('payment', 'Cheque / bank collection', None, self.sr)])
        self.assertEqual(st['closing'], 1000 + 178088 - 20000)
        # The period from 2026: everything before is the opening balance.
        period = finance.get('/api/finance/accounts/statement?client_id=%d&start=2026-01-20' % self.client_id).get_json()
        self.assertEqual((period['opening'], len(period['entries'])), (1000 + 178088.0, 1))
        by_client = finance.get('/api/finance/accounts/balances?group=client').get_json()
        mine = next(r for r in by_client['rows'] if r['id'] == self.client_id)
        self.assertEqual((mine['debit'], mine['credit'], mine['closing']), (179088.0, 20000.0, 159088.0))
        xlsx = finance.get('/api/finance/accounts/statement?format=xlsx&client_id=%d' % self.client_id)
        self.assertEqual(xlsx.status_code, 200)
        self.assertEqual(self._web(self.account).post('/api/finance/accounts/opening', json={
            'client_id': self.client_id, 'as_of': '2024-12-31', 'amount': 1}).status_code, 403)


class InvoiceSeriesTest(InvoiceFlowTest):
    """Finance sets where the series continues; drafts take the next number from there."""

    def test_series_floor(self):
        finance, author = self._web(self.finance), self._web(self.account)
        r = finance.post('/api/invoice-series', json={'next_number': 99553})
        self.assertEqual(r.get_json()['next_number'], 99553)
        inv_id, _ = self._draft(author)
        self.assertEqual(author.get('/api/invoices/%d' % inv_id).get_json()['invoice']['invoice_number'], 99553)
        self.assertEqual(finance.post('/api/invoice-series', json={'next_number': 5}).status_code, 400)  # behind used numbers
        self.assertEqual(author.post('/api/invoice-series', json={'next_number': 999999}).status_code, 403)



class RefundAndMoneyTest(InvoiceFlowTest):
    """Posting books the money in a payment method; refunds credit the client for chosen items."""

    def _pm_balance(self):
        cur = self._cursor()
        cur.execute("SELECT current_balance FROM payment_methods WHERE id = %s", (self.pm,))
        return float(cur.fetchone()['current_balance'])

    def _posted(self, number, amount):
        author, finance = self._web(self.account), self._web(self.finance)
        inv_id, _ = self._draft(author)
        author.post('/api/invoices/%d/submit' % inv_id)
        r = finance.post('/api/invoices/%d/post' % inv_id, json={'invoice_number': number, 'payment_method_id': self.pm, 'amount': amount})
        self.assertEqual(r.status_code, 200, r.get_json())
        return inv_id

    def test_posting_books_the_invoice_not_money(self):
        author, finance = self._web(self.account), self._web(self.finance)
        inv_id, _ = self._draft(author)
        author.post('/api/invoices/%d/submit' % inv_id)
        before = self._pm_balance()
        tree_before = finance.get('/api/finance/tree').get_json()
        r = finance.post('/api/invoices/%d/post' % inv_id, json={'invoice_number': 98200})   # no payment method
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual((r.get_json()['amount'], self._pm_balance()), (0.0, before))       # no money moved
        # In the Finance Tree, as double entry: Dr 1103 178,088 + Dr 1107 1,576 = Cr 4101 157,600 + Cr 2103 22,064.
        tree = finance.get('/api/finance/tree').get_json()
        self.assertTrue(tree['balanced'])
        moved = lambda code, side: round(branding_gate.chart_find(tree['classes'], code)[side]
                                         - branding_gate.chart_find(tree_before['classes'], code)[side], 2)
        self.assertEqual([moved('1103', 'debit'), moved('1107', 'debit'), moved('4101', 'credit'), moved('2103', 'credit'),
                          moved('1103', 'credit'), moved('1101', 'debit')],
                         [178088.0, 1576.0, 157600.0, 22064.0, 0.0, 0.0])
        st = finance.get('/api/finance/accounts/statement?client_id=%d' % self.client_id).get_json()
        self.assertEqual((st['debit'], st['credit'], st['closing']), (178088.0, 0.0, 178088.0))   # owed

    def test_posting_with_money_still_books_it(self):
        author, finance = self._web(self.account), self._web(self.finance)
        inv_id, _ = self._draft(author)
        author.post('/api/invoices/%d/submit' % inv_id)
        self.assertEqual(finance.post('/api/invoices/%d/post' % inv_id, json={
            'invoice_number': 98201, 'payment_method_id': self.pm, 'amount': 999999}).status_code, 400)  # over the total
        before = self._pm_balance()
        r = finance.post('/api/invoices/%d/post' % inv_id, json={'invoice_number': 98201, 'payment_method_id': self.pm})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(round(self._pm_balance() - before, 2), 178088.0)
        st = finance.get('/api/finance/accounts/statement?client_id=%d' % self.client_id).get_json()
        self.assertEqual((st['debit'], st['credit'], st['closing']), (178088.0, 178088.0, 0.0))

    def test_refund_chosen_items_in_full(self):
        finance = self._web(self.finance)
        inv_id = self._posted(98300, 0)                          # owed, not paid
        got = finance.get('/api/invoices/%d' % inv_id).get_json()['invoice']
        stage = next(l for l in got['refundable'] if l['description'] == 'stage')
        self.assertTrue(got['can_refund'])
        none = finance.post('/api/invoices/%d/refund' % inv_id, json={'lines': []})
        self.assertEqual(none.status_code, 400)
        # A ticked item is refunded whole; a partial quantity sent is ignored.
        r = finance.post('/api/invoices/%d/refund' % inv_id, json={'lines': [{'refund_of_line': stage['id'], 'qty': 0.5}],
                                                                  'notes': 'stage not used'})
        self.assertEqual(r.status_code, 200, r.get_json())
        refund = r.get_json()
        # stage 52,000 + VAT 7,280 - 1% 520 = 58,760
        self.assertEqual(refund['total'], 58760.0)
        again = finance.post('/api/invoices/%d/refund' % inv_id, json={'lines': [{'refund_of_line': stage['id'], 'qty': 1}]})
        self.assertEqual(again.status_code, 400)                  # nothing left of stage to refund
        # Finance posts its own refund draft, nothing paid back (the client had not paid).
        post = finance.post('/api/invoices/%d/post' % refund['id'], json={'payment_method_id': self.pm, 'amount': 0})
        self.assertEqual(post.status_code, 200, post.get_json())
        st = finance.get('/api/finance/accounts/statement?client_id=%d' % self.client_id).get_json()
        kinds = [(e['kind'], e['debit'], e['credit']) for e in st['entries']]
        self.assertEqual(kinds, [('invoice', 178088.0, 0.0), ('refund', 0.0, 58760.0)])
        self.assertEqual(st['closing'], 178088.0 - 58760.0)
        acc = finance.get('/api/finance/accounts?client_id=%d' % self.client_id).get_json()['clients'][0]
        self.assertEqual((acc['invoiced'], acc['refunded'], acc['balance_due']), (119328.0, 58760.0, 119328.0))

    def test_refund_of_a_paid_invoice_pays_money_back(self):
        finance = self._web(self.finance)
        inv_id = self._posted(98400, 178088)                     # paid in full on posting
        got = finance.get('/api/invoices/%d' % inv_id).get_json()['invoice']
        led = next(l for l in got['refundable'] if l['description'] == 'LED Screen')
        refund = finance.post('/api/invoices/%d/refund' % inv_id, json={'lines': [{'refund_of_line': led['id'], 'qty': 1}]}).get_json()
        before = self._pm_balance()
        r = finance.post('/api/invoices/%d/post' % refund['id'], json={'payment_method_id': self.pm})   # full amount back
        self.assertEqual(r.status_code, 200, r.get_json())
        # LED 105,600 + 14,784 - 1,056 = 119,328 paid back out of the box.
        self.assertEqual(round(before - self._pm_balance(), 2), 119328.0)
        st = finance.get('/api/finance/accounts/statement?client_id=%d' % self.client_id).get_json()
        self.assertEqual(st['closing'], 0.0)
        self.assertEqual([e['kind'] for e in st['entries']], ['invoice', 'refund', 'payment', 'refund_paid'])
