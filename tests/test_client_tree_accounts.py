"""
Clients in the Finance Tree (Ahmed, 2026-11-11): each client its own account
under 1103 (11031, 11032, ... in the order added), carrying their invoices,
collections and refunds; 1103 is their sum, and a client's account matches
their statement. Rolled back.
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


class ClientTreeAccountsTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db=testdb.DB, charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self.raw.cursor(MySQLdb.cursors.DictCursor))
        branding_gate.app.config['TESTING'] = True
        self.cur = self.raw.cursor(MySQLdb.cursors.DictCursor)
        self.cur.execute("SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id "
                         "WHERE r.code = 'finance_manager' AND u.is_active = 1 LIMIT 1")
        uid = self.cur.fetchone()['id']
        perms, role = branding_gate.load_permissions(uid)
        self.web = branding_gate.app.test_client()
        with self.web.session_transaction() as s:
            s.update({'user_id': uid, 'mobile': 'm', 'email': 'e', 'username': 'u', 'name': 'T',
                      'roles': [role], 'perms': perms, 'role_code': role})

    def _undo(self):
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def test_new_clients_take_the_next_code(self):
        self.cur.execute("SELECT MAX(CAST(SUBSTRING(account_code, 5) AS UNSIGNED)) AS n FROM client")
        last = self.cur.fetchone()['n']
        self.cur.execute("SELECT parent_company_id FROM client LIMIT 1")
        company = self.cur.fetchone()['parent_company_id']
        self.cur.execute("INSERT INTO client (client_name, parent_company_id, mobile_number, email_address, added_by) "
                         "VALUES ('Tree T', %s, '01099999999', 'tree@t.t', 't')", (company,))
        new = self.cur.lastrowid
        branding_gate.assign_client_accounts(self.cur)
        self.cur.execute("SELECT account_code FROM client WHERE id = %s", (new,))
        self.assertEqual(self.cur.fetchone()['account_code'], '1103%d' % (last + 1))

    def test_1103_is_its_clients_and_each_matches_its_statement(self):
        tree = self.web.get('/api/finance/tree').get_json()
        self.assertTrue(tree['balanced'])
        node = branding_gate.chart_find(tree['classes'], '1103')
        kids = [k for k in node['children'] if k.get('client')]
        self.assertTrue(kids)
        self.assertTrue(all(k['code'].startswith('1103') and len(k['code']) > 4 for k in kids))
        self.assertAlmostEqual(node['debit'], sum(k['debit'] for k in node['children']), places=2)
        self.assertAlmostEqual(node['credit'], sum(k['credit'] for k in node['children']), places=2)
        for k in kids:
            if k['debit'] or k['credit']:
                st = branding_gate.account_statement(self.cur, client_id=k['client'])
                self.assertAlmostEqual(k['value'], st['closing'], places=2, msg=k['code'])

    def test_a_custody_leg_is_not_a_collection(self):
        # Approving a staff expense books an income leg on 111002 that names the
        # client; it was read as money collected from them (tadros: 700).
        self.cur.execute("SELECT id FROM client ORDER BY id LIMIT 1")
        client = self.cur.fetchone()['id']
        self.cur.execute("SELECT id FROM payment_methods WHERE is_active = 1 LIMIT 1")
        pm = self.cur.fetchone()['id']
        before = branding_gate.account_statement(self.cur, client_id=client)['credit']
        collected = self.web.get('/api/finance/accounts?client_id=%d' % client).get_json()['clients'][0]['collected']
        self.cur.execute("""INSERT INTO finance_transactions (transaction_code, transaction_type, amount, payment_method_id,
                           category_id, client_id, transaction_date, status, added_by)
                       VALUES ('T-CUST', 'income', 450, %s, 44, %s, '2026-11-01', 'approved', 't')""", (pm, client))
        self.assertEqual(branding_gate.account_statement(self.cur, client_id=client)['credit'], before)
        self.assertEqual(self.web.get('/api/finance/accounts?client_id=%d' % client).get_json()['clients'][0]['collected'],
                         collected)

    def test_the_client_report_carries_the_code(self):
        self.cur.execute("SELECT id, account_code FROM client ORDER BY id LIMIT 1")
        c = self.cur.fetchone()
        body = self.web.get('/api/finance/accounts?client_id=%d' % c['id']).get_json()
        self.assertEqual(body['clients'][0]['account_code'], c['account_code'])


if __name__ == '__main__':
    unittest.main()
