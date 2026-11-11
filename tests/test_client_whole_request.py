"""
Client approves or rejects the whole request at once (David Osama, 2026-11-11).

Request #510 sent one "Client rejected: ..." notification per item. Approve all /
Reject all decide every item still waiting in one go and tell Operations once,
naming the request. Per-item decisions stay as they were. Rolled back.
"""

import testdb  # noqa: F401  first: the test database, not the live one
import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate
import fixtures


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def close(self): pass
    def rollback(self): pass


class WholeRequestDecisionTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db=testdb.DB, charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = (branding_gate.connection, branding_gate.notify_users)
        self.told = []
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self._cursor())
        branding_gate.notify_users = lambda users, title, content, link=None, category=None, action=None: \
            self.told.append((title, content))
        self.addCleanup(self._undo)
        cur = self._cursor()
        cur.execute("SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id "
                    "WHERE r.code = 'admin' AND u.is_active = 1 LIMIT 1")
        self.admin = cur.fetchone()['id']
        client_id = fixtures.ensure_client(cur)
        cur.execute("INSERT INTO sales_request (client_id, title, start_date, created_by, owner_user_id) "
                    "VALUES (%s, 'SAM', CURDATE(), 'test', %s)", (client_id, self.admin))
        self.request_id = cur.lastrowid
        self.items = []
        for name, status, sell in (('Stage', 'submitted', 100), ('Screen', 'submitted', 200), ('Truss', 'submitted', 300),
                                   ('Decided', 'approved', 50), ('Unpriced', 'submitted', None)):
            cur.execute("""INSERT INTO sales_request_items (request_id, name, qty, cost_per_item, sell_per_item, total_sell,
                               approval_status) VALUES (%s, %s, 1, 10, %s, %s, %s)""",
                        (self.request_id, name, sell, sell, status))
            self.items.append(cur.lastrowid)

    def _undo(self):
        branding_gate.connection, branding_gate.notify_users = self.original
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

    def _statuses(self):
        cur = self._cursor()
        cur.execute("SELECT name, approval_status, client_feedback FROM sales_request_items WHERE request_id = %s",
                    (self.request_id,))
        return {r['name']: (r['approval_status'], r['client_feedback']) for r in cur.fetchall()}

    def _decide(self, decision, feedback=''):
        return self._web(self.admin).post('/api/client-approval/requests/%d/decide' % self.request_id,
                                          json={'decision': decision, 'feedback': feedback})

    def test_reject_all_decides_the_open_items_and_tells_operations_once(self):
        self.assertEqual(self._decide('rejected').status_code, 400)            # a reason is required
        r = self._decide('rejected', 'Budget cut')
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()['decided'], 3)
        s = self._statuses()
        self.assertEqual([s[n][0] for n in ('Stage', 'Screen', 'Truss')], ['rejected'] * 3)
        self.assertEqual(s['Stage'][1], 'Budget cut')
        self.assertEqual((s['Decided'][0], s['Unpriced'][0]), ('approved', 'submitted'))   # untouched
        self.assertEqual(len(self.told), 1)
        title, body = self.told[0]
        self.assertIn('whole request #%d (SAM)' % self.request_id, title)
        self.assertIn('Budget cut', body)
        self.assertEqual(self._decide('rejected', 'again').status_code, 400)  # nothing left waiting

    def test_approve_all_sends_one_notice(self):
        r = self._decide('approved')
        self.assertEqual(r.get_json()['decided'], 3)
        self.assertEqual(len(self.told), 1)
        self.assertIn('approved', self.told[0][0])

    def test_a_single_reject_keeps_its_reason(self):
        r = self._web(self.admin).post('/api/client-approval/items/%d/reject' % self.items[0],
                                       json={'rejected': True, 'reason': 'Too expensive'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._statuses()['Stage'], ('rejected', 'Too expensive'))


if __name__ == '__main__':
    unittest.main()
