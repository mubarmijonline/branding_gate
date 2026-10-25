"""
A manager rejects (and approves) their own people's expenses, until Finance
has paid them; someone else's are refused and not listed. Rollback-based.
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


class ManagerRejectTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self.raw.cursor(MySQLdb.cursors.DictCursor))
        branding_gate.app.config['TESTING'] = True
        cur = self.raw.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("""SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
                       WHERE u.is_active = 1 AND r.code = 'operations_manager' ORDER BY u.id LIMIT 1""")
        self.manager = cur.fetchone()['id']
        perms, role = branding_gate.load_permissions(self.manager)
        self.web = branding_gate.app.test_client()
        with self.web.session_transaction() as s:
            s.update({'user_id': self.manager, 'mobile': 'm', 'email': 'e', 'username': 'u', 'name': 'T',
                      'roles': [role], 'perms': perms, 'role_code': role})
        with branding_gate.app.test_request_context():
            branding_gate.session.update({'user_id': self.manager, 'perms': perms})
            team = branding_gate.visible_user_ids('expense_tracking.reject')
        cur.execute("SELECT id FROM user WHERE is_active = 1 ORDER BY id")
        everyone = [r['id'] for r in cur.fetchall()]
        self.mine = next(u for u in everyone if u in team and u != self.manager)
        self.other = next(u for u in everyone if u not in team)
        self.ids = {}
        for key, uid, status in (('mine', self.mine, 'submitted'), ('mine_sent', self.mine, 'manager_approved'),
                                 ('mine_paid', self.mine, 'approved'), ('other', self.other, 'submitted')):
            cur.execute("""INSERT INTO user_expense_tracking (user_id, tracking_code, amount, description, status, submitted_at, expense_date)
                           VALUES (%s, %s, 10, 't', %s, NOW(), CURDATE())""", (uid, 'T-' + key, status))
            self.ids[key] = cur.lastrowid

    def _undo(self):
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _reject(self, key):
        return self.web.post('/api/finance/expense-approvals/%d/reject' % self.ids[key], json={'reason': 'no receipt'})

    def test_reject_within_team_until_paid(self):
        self.assertEqual(self._reject('mine').status_code, 200)
        self.assertEqual(self._reject('mine_sent').status_code, 200)       # with Finance, not paid yet
        self.assertEqual(self._reject('mine_paid').status_code, 404)       # paid: no longer rejectable
        self.assertEqual(self._reject('other').status_code, 403)
        listed = [e['id'] for e in self.web.get('/api/finance/expense-approvals?status=submitted').get_json()['expenses']]
        self.assertNotIn(self.ids['other'], listed)
        self.assertEqual(self.web.post('/api/finance/expense-approvals/%d/approve' % self.ids['other'], json={}).status_code, 403)


if __name__ == '__main__':
    unittest.main()
