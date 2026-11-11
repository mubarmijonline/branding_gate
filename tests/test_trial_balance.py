"""
Trial balance (Ahmed, 2026-11-11): every account's opening balance, the
period's debits and credits, and its closing balance, for a month, quarter,
year or any dates. Read-only over the test database.
"""

import testdb  # noqa: F401  first: the test database, not the live one
import datetime
import unittest

import branding_gate


class TrialBalanceTest(unittest.TestCase):

    def setUp(self):
        branding_gate.app.config['TESTING'] = True
        self.conn, self.cur = branding_gate.connection()
        self.addCleanup(self.conn.close)
        self.cur.execute("SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id "
                         "WHERE r.code = 'finance_manager' AND u.is_active = 1 LIMIT 1")
        uid = self.cur.fetchone()['id']
        perms, role = branding_gate.load_permissions(uid)
        self.web = branding_gate.app.test_client()
        with self.web.session_transaction() as s:
            s.update({'user_id': uid, 'mobile': 'm', 'email': 'e', 'username': 'u', 'name': 'T',
                      'roles': [role], 'perms': perms, 'role_code': role})

    def test_opening_plus_movement_is_closing_and_it_balances(self):
        body = self.web.get('/api/finance/trial-balance?start_date=2026-11-01&end_date=2026-11-30').get_json()
        self.assertTrue(body['success'], body)
        self.assertTrue(body['balanced'], body['totals'])
        for r in body['rows']:
            net = r['opening_debit'] - r['opening_credit'] + r['debit'] - r['credit']
            self.assertAlmostEqual(net, r['closing_debit'] - r['closing_credit'], places=2, msg=r['code'])
            self.assertFalse(r['opening_debit'] and r['opening_credit'], r['code'])   # one side only

    def test_one_period_closes_where_the_next_opens(self):
        rows, _ = branding_gate.trial_balance(self.cur, datetime.date(2026, 10, 1), datetime.date(2026, 10, 31))
        nxt, _ = branding_gate.trial_balance(self.cur, datetime.date(2026, 11, 1), datetime.date(2026, 11, 30))
        closing = {r['id']: (r['closing_debit'], r['closing_credit']) for r in rows}
        for r in nxt:
            self.assertEqual(closing[r['id']], (r['opening_debit'], r['opening_credit']), r['code'])

    def test_whole_history_matches_the_tree(self):
        rows, totals = branding_gate.trial_balance(self.cur, datetime.date(2000, 1, 1), datetime.date(2100, 12, 31))
        self.assertEqual((totals['opening_debit'], totals['opening_credit']), (0, 0))
        tree = self.web.get('/api/finance/tree').get_json()
        self.assertAlmostEqual(totals['debit'], tree['debit'], places=2)
        self.assertEqual({r['code'] for r in rows if r['depth'] == 0}, {c['code'] for c in tree['classes']})

    def test_bad_dates_are_refused(self):
        self.assertEqual(self.web.get('/api/finance/trial-balance?start_date=2026-12-01&end_date=2026-11-01').status_code, 400)
        self.assertEqual(self.web.get('/api/finance/trial-balance').status_code, 400)
        r = self.web.get('/api/finance/trial-balance?start_date=2026-11-01&end_date=2026-11-30&format=xlsx')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data[:2] == b'PK')


if __name__ == '__main__':
    unittest.main()
