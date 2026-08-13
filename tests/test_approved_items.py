"""
An assignment is a commitment: making one and rewriting one are different acts.

Rollback-based, like the other route tests here.
"""

import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate
import fixtures
import rbac


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def close(self): pass
    def rollback(self): pass


class AssignmentLockTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self._cursor())

        cur = self._cursor()
        cur.execute("SELECT id FROM department WHERE code = 'operations'")
        self.department_id = cur.fetchone()['id']
        self.roles = {}
        for code in ('operations_manager', 'operations_team_leader'):
            cur.execute("SELECT id FROM rbac_role WHERE code = %s", (code,))
            self.roles[code] = cur.fetchone()['id']
        self.head = self._user('lock-head', 'operations_manager')
        self.leader = self._user('lock-leader', 'operations_team_leader')

        client_id = fixtures.ensure_client(cur)
        cur.execute("""INSERT INTO sales_request (client_id, title, start_date, created_by,
                                                  items_count, owner_user_id)
                       VALUES (%s, 'Assignment lock test', CURDATE(), 'test', 1, %s)""",
                    (client_id, self.head))
        self.request_id = cur.lastrowid
        cur.execute("""INSERT INTO sales_request_items (request_id, name, qty, approval_status)
                       VALUES (%s, 'Lock test item', 1, 'approved')""", (self.request_id,))
        self.item_id = cur.lastrowid
        self.suppliers = fixtures.ensure_suppliers(cur, 2)
        cur.close()

    def tearDown(self):
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _user(self, username, role_code):
        cur = self._cursor()
        cur.execute("""INSERT INTO user (name, mobile, email, password, username, title,
                                         department_id, rbac_role_id, date)
                       VALUES (%s, %s, %s, 'x', %s, 'Lock Test', %s, %s, NOW())""",
                    (username, '019%08d' % (abs(hash(username)) % 10**8),
                     username + '@example.com', username, self.department_id,
                     self.roles[role_code]))
        user_id = cur.lastrowid
        cur.close()
        return user_id

    def _client_for(self, user_id):
        perms, role_code = branding_gate.load_permissions(user_id)
        client = branding_gate.app.test_client()
        with client.session_transaction() as flask_session:
            flask_session.update({"user_id": user_id, "mobile": "m", "email": "e",
                                  "username": "u", "name": "n", "roles": [role_code],
                                  "perms": perms, "role_code": role_code})
        return client

    def _assign(self, actor, supplier_id):
        return self._client_for(actor).put(
            '/api/approved-items/%d/supplier' % self.item_id,
            json={'supplier_id': supplier_id, 'due_date': '2026-09-01'})

    def test_a_leader_may_make_the_first_assignment(self):
        if not self.suppliers:
            self.skipTest('no suppliers in this database')
        self.assertEqual(self._assign(self.leader, self.suppliers[0]).status_code, 200)

    def test_a_leader_may_not_rewrite_it_afterwards(self):
        if len(self.suppliers) < 2:
            self.skipTest('need two suppliers')
        self._assign(self.leader, self.suppliers[0])
        second = self._assign(self.leader, self.suppliers[1])
        self.assertEqual(second.status_code, 403)
        self.assertIn('Operations Manager', second.get_json()['error'])

        cur = self._cursor()
        cur.execute("SELECT supplier_id FROM sales_request_items WHERE id = %s", (self.item_id,))
        self.assertEqual(cur.fetchone()['supplier_id'], self.suppliers[0])
        cur.close()

    def test_the_head_may_rewrite_it(self):
        if len(self.suppliers) < 2:
            self.skipTest('need two suppliers')
        self._assign(self.leader, self.suppliers[0])
        self.assertEqual(self._assign(self.head, self.suppliers[1]).status_code, 200)
        cur = self._cursor()
        cur.execute("SELECT supplier_id FROM sales_request_items WHERE id = %s", (self.item_id,))
        self.assertEqual(cur.fetchone()['supplier_id'], self.suppliers[1])
        cur.close()


class PipelinePolicyTest(unittest.TestCase):

    def test_only_the_head_and_admin_rewrite_an_assignment(self):
        holders = [role for role, grants in rbac.SEED_MATRIX.items()
                   if 'approved_item.reassign' in grants]
        self.assertEqual(sorted(holders), ['admin', 'operations_manager'])

    def test_the_floor_can_still_make_an_assignment(self):
        for role in ('operations_manager', 'operations_team_leader'):
            self.assertIn('approved_item.edit', rbac.SEED_MATRIX[role], role)


if __name__ == '__main__':
    unittest.main()
