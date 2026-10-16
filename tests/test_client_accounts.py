"""
Client Accounts, and money that must belong to someone.

A Client Payment (FIN202610-59779, EGP 20,000) was saved with no client and no
sales request, so it counted for nobody. A Client Payment now has to name its
SR, the client comes from the SR, and the old ones can be linked afterwards.
The Client Accounts page and its workbook show, per company, client and
request: quoted, client-approved, collected, pending and outstanding.

Rollback-based, like the other route tests here.
"""

import io
import unittest

import MySQLdb
import MySQLdb.cursors
import openpyxl

import branding_gate


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def close(self): pass


class ClientAccountsTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self._cursor())
        branding_gate.app.config['TESTING'] = True

        cur = self._cursor()
        cur.execute("""SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
                       WHERE r.code = 'finance_manager' AND u.is_active = 1 ORDER BY u.id LIMIT 1""")
        self.finance_id = cur.fetchone()['id']

        cur.execute("""INSERT INTO company (company_name, industry_sector, address, email_address,
                       phone_number, primary_contact_person, added_by)
                       VALUES ('Acme Test Co 7q', 'Pharma', '-', 'a@x', '0', '-', 't')""")
        self.company_id = cur.lastrowid
        self.client_ids = []
        for name in ('Client A 7q', 'Client B 7q'):
            cur.execute("""INSERT INTO client (client_name, parent_company_id, email_address,
                           mobile_number, added_by) VALUES (%s, %s, 'c@x', '0', 't')""",
                        (name, self.company_id))
            self.client_ids.append(cur.lastrowid)
        cur.execute("""INSERT INTO sales_request (client_id, company_id, title, created_by, start_date, status)
                       VALUES (%s, %s, 'Booth 7q', 't', '2026-10-01', 'submitted')""",
                    (self.client_ids[0], self.company_id))
        self.sr_id = cur.lastrowid
        for name, sell, cost, status in (('Approved item', 1000, 600, 'approved'),
                                         ('Pending item', 500, 300, 'pending')):
            cur.execute("""INSERT INTO sales_request_items (request_id, name, total_sell, total_cost, approval_status)
                           VALUES (%s, %s, %s, %s, %s)""", (self.sr_id, name, sell, cost, status))
        cur.execute("""INSERT INTO payment_methods (method_name, method_code, method_type, current_balance)
                       VALUES ('Test Safe 7q', 'TEST_SAFE_7Q', 'cash', 0)""")
        self.pm_id = cur.lastrowid
        cur.close()

    def _undo(self):
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _client_for(self, user_id):
        perms, role_code = branding_gate.load_permissions(user_id)
        client = branding_gate.app.test_client()
        with client.session_transaction() as s:
            s.update({'user_id': user_id, 'mobile': 'm', 'email': 'e', 'username': 'u',
                      'name': 'Tester', 'roles': [role_code], 'perms': perms, 'role_code': role_code})
        return client

    def _tx(self, amount, status='approved', category=1, sr=None, client=None, ttype='income'):
        cur = self._cursor()
        cur.execute("""INSERT INTO finance_transactions (transaction_code, transaction_type, amount,
                       payment_method_id, category_id, client_id, sales_request_id, transaction_date,
                       status, added_by) VALUES (%s, %s, %s, %s, %s, %s, %s, '2026-10-05', %s, 't')""",
                    ('T7Q-%s-%s' % (amount, status), ttype, amount, self.pm_id, category, client, sr, status))
        tx_id = cur.lastrowid
        cur.close()
        return tx_id

    # --- the rule ---

    def test_client_payment_needs_its_request(self):
        cur = self._cursor()
        self.assertIsNotNone(branding_gate.link_transaction_to_request(cur, 1, None, None)[1])
        self.assertEqual(branding_gate.link_transaction_to_request(cur, 2, None, None), (None, None))
        self.assertEqual(branding_gate.link_transaction_to_request(cur, 1, None, self.sr_id),
                         (self.client_ids[0], None))
        self.assertIn('different client',
                      branding_gate.link_transaction_to_request(cur, 1, self.client_ids[1], self.sr_id)[1])
        self.assertIn('not found', branding_gate.link_transaction_to_request(cur, 1, None, 999999999)[1])

    def test_create_route_refuses_unlinked_client_payment_and_fills_client(self):
        web = self._client_for(self.finance_id)
        body = {'transaction_type': 'income', 'amount': 100, 'payment_method_id': self.pm_id,
                'category_id': 1}
        r = web.post('/api/finance/transactions', json=body)
        self.assertEqual(r.status_code, 400, r.get_json())
        r = web.post('/api/finance/transactions', json=dict(body, sales_request_id=self.sr_id))
        self.assertEqual(r.status_code, 200, r.get_json())
        cur = self._cursor()
        cur.execute("SELECT client_id FROM finance_transactions WHERE sales_request_id = %s", (self.sr_id,))
        self.assertEqual(cur.fetchone()['client_id'], self.client_ids[0])

    def test_link_an_old_payment(self):
        tx = self._tx(20000)
        web = self._client_for(self.finance_id)
        r = web.post('/api/finance/transactions/%d/link-request' % tx,
                     json={'sales_request_id': 'SR-%d' % self.sr_id})
        self.assertEqual(r.status_code, 200, r.get_json())
        cur = self._cursor()
        cur.execute("SELECT client_id, sales_request_id FROM finance_transactions WHERE id = %s", (tx,))
        self.assertEqual(cur.fetchone(), {'client_id': self.client_ids[0], 'sales_request_id': self.sr_id})
        cur.execute("SELECT notes FROM finance_approval_log WHERE transaction_id = %s", (tx,))
        self.assertEqual(cur.fetchone()['notes'], 'Linked to SR-%d' % self.sr_id)
        again = web.post('/api/finance/transactions/%d/link-request' % tx, json={'sales_request_id': self.sr_id})
        self.assertEqual(again.status_code, 400)

    # --- the figures ---

    def test_figures_roll_up_request_client_company(self):
        self._tx(300, sr=self.sr_id)                      # collected, client via SR
        self._tx(200, status='pending', category=2, client=self.client_ids[0])   # pending
        self._tx(999, status='rejected', sr=self.sr_id)    # ignored in sums
        self._tx(150, category=10, sr=self.sr_id, ttype='expense')               # paid out
        web = self._client_for(self.finance_id)
        res = web.get('/api/finance/accounts?company_id=%d' % self.company_id).get_json()
        co = res['companies'][0]
        self.assertEqual((co['quoted_sell'], co['approved_sell'], co['collected'], co['pending_in'],
                          co['outstanding'], co['paid_out'], co['expected_margin'], co['clients_count']),
                         (1500.0, 1000.0, 300.0, 200.0, 700.0, 150.0, 400.0, 2))
        a = next(c for c in res['clients'] if c['id'] == self.client_ids[0])
        b = next(c for c in res['clients'] if c['id'] == self.client_ids[1])
        self.assertEqual((a['collected'], a['transactions']), (300.0, 4))
        self.assertEqual((b['requests'], b['outstanding']), (0, 0.0))
        self.assertEqual(res['requests'][0]['collected'], 300.0)
        self.assertEqual(len(res['items']), 2)
        self.assertEqual(len(res['transactions']), 4)

    def test_unlinked_payment_listed_on_overview(self):
        tx = self._tx(20000)
        web = self._client_for(self.finance_id)
        res = web.get('/api/finance/accounts').get_json()
        self.assertIn(tx, [u['id'] for u in res['unlinked']])

    def test_date_range_filters_transactions(self):
        self._tx(300, sr=self.sr_id)
        web = self._client_for(self.finance_id)
        res = web.get('/api/finance/accounts?company_id=%d&start=2026-10-06' % self.company_id).get_json()
        self.assertEqual(res['companies'][0]['collected'], 0.0)

    def test_report_workbook(self):
        self._tx(300, sr=self.sr_id)
        web = self._client_for(self.finance_id)
        r = web.get('/api/finance/accounts/report?client_id=%d' % self.client_ids[0])
        self.assertEqual(r.status_code, 200)
        book = openpyxl.load_workbook(io.BytesIO(r.data))
        self.assertEqual(book.sheetnames, ['Companies', 'Clients', 'Requests', 'Items', 'Transactions'])
        rows = list(book['Requests'].values)
        self.assertEqual(rows[1][rows[0].index('Collected')], 300)
        self.assertEqual(rows[1][rows[0].index('Client')], 'Client A 7q')

    def test_pages_and_access(self):
        web = self._client_for(self.finance_id)
        self.assertEqual(web.get('/finance/accounts').status_code, 200)
        page = web.get('/finance/accounts/company/%d' % self.company_id)
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'Client Accounts', page.data)
        self.assertEqual(web.get('/finance/accounts/other/1').status_code, 404)
        self.assertEqual(web.get('/api/finance/accounts?client_id=999999999').status_code, 404)
        cur = self._cursor()
        cur.execute("""SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
                       WHERE r.code = 'operations_member' AND u.is_active = 1 LIMIT 1""")
        ops = self._client_for(cur.fetchone()['id'])
        self.assertEqual(ops.get('/api/finance/accounts').status_code, 403)


if __name__ == '__main__':
    unittest.main()
