"""
The custody figure a person sees moves with every expense.

George's ask: the moment an expense is added it comes off what the member
sees -- on My Expenses and in the top bar -- without waiting for anyone. A
manager or Finance changing the amount moves the figure; a refusal hands it
back; Finance approving books it. Stage counts sit on the page. Rollback-based.
"""

import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def close(self): pass


class CustodyTest(unittest.TestCase):

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
                       WHERE r.code = 'operations_member' AND u.is_active = 1 ORDER BY u.id LIMIT 1""")
        self.member = cur.fetchone()['id']
        cur.execute("DELETE FROM user_expense_tracking WHERE user_id = %s", (self.member,))
        cur.execute("""INSERT INTO user_finance_balances (user_id, balance) VALUES (%s, 4000)
                       ON DUPLICATE KEY UPDATE balance = 4000""", (self.member,))
        cur.close()

    def _undo(self):
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    _n = iter(range(1, 999))

    def _expense(self, amount, status):
        cur = self._cursor()
        cur.execute("""INSERT INTO user_expense_tracking (user_id, tracking_code, supplier_name, amount, requested_amount,
                       description, expense_date, status) VALUES (%s, %s, 'Transportation', %s, %s, 't', '2026-10-18', %s)""",
                    (self.member, 'EXP-C%d' % next(self._n), amount, amount, status))
        return cur.lastrowid

    def _web(self):
        perms, role = branding_gate.load_permissions(self.member)
        web = branding_gate.app.test_client()
        with web.session_transaction() as s:
            s.update({'user_id': self.member, 'mobile': 'm', 'email': 'e', 'username': 'u', 'name': 'T',
                      'roles': [role], 'perms': perms, 'role_code': role})
        return web

    def test_george_example(self):
        # 4,000 held; 500 spent and with the manager: 3,500 shows at once.
        exp = self._expense(500, 'submitted')
        web = self._web()
        self.assertEqual(web.get('/api/finance/my-balance').get_json()['available'], 3500.0)
        # The manager allows 300 of it: 3,700.
        cur = self._cursor()
        cur.execute("UPDATE user_expense_tracking SET amount = 300, status = 'manager_approved' WHERE id = %s", (exp,))
        self.assertEqual(web.get('/api/finance/my-balance').get_json()['available'], 3700.0)
        # Finance allows 200: 3,800, still awaiting.
        cur.execute("UPDATE user_expense_tracking SET amount = 200 WHERE id = %s", (exp,))
        page = web.get('/api/my-expenses').get_json()
        self.assertEqual((page['future_balance'], page['pending_total']), (3800.0, 200.0))
        # Refused outright: all of it back.
        cur.execute("UPDATE user_expense_tracking SET status = 'rejected' WHERE id = %s", (exp,))
        self.assertEqual(web.get('/api/finance/my-balance').get_json()['available'], 4000.0)

    def test_stage_counts(self):
        for amount, status in ((100, 'draft'), (200, 'draft'), (50, 'submitted'), (70, 'manager_approved'),
                               (90, 'approved'), (10, 'rejected')):
            self._expense(amount, status)
        stages = self._web().get('/api/my-expenses').get_json()['stages']
        self.assertEqual({k: (v['count'], v['amount']) for k, v in stages.items()}, {
            'draft': (2, 300.0), 'submitted': (1, 50.0), 'manager_approved': (1, 70.0),
            'approved': (1, 90.0), 'rejected': (1, 10.0)})


if __name__ == '__main__':
    unittest.main()
