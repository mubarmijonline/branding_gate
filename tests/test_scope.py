"""
Row-level scope, end to end against the real schema.

Follows the harness in test_negotiation_routes.py: a real connection with
autocommit off, branding_gate.connection monkeypatched to hand out a wrapper
whose commit() is a no-op, and a rollback in tearDown. Nothing survives.

Unlike the negotiation tests, these call handlers through the decorator,
because the decorator and the scope predicate are what is under test.
"""

import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate
import rbac


class _RollbackConnection:
    def __init__(self, raw_connection):
        self.raw_connection = raw_connection

    def commit(self):
        pass

    def close(self):
        pass

    def rollback(self):
        self.raw_connection.rollback()


class ScopeTest(unittest.TestCase):
    """A head sees the department, a leader their team, a member only their own."""

    def setUp(self):
        self.raw_connection = MySQLdb.connect(
            host="localhost", user="ps", passwd="Aa@123456", db="branding_gate",
            port=3306, charset="utf8mb4", use_unicode=True,
        )
        self.raw_connection.autocommit(False)
        self.wrapper = _RollbackConnection(self.raw_connection)
        self.original_connection = branding_gate.connection
        branding_gate.connection = self._connection

        cur = self._cursor()
        cur.execute("SELECT id FROM department WHERE code = 'sales'")
        self.department_id = cur.fetchone()["id"]
        self.roles = {}
        for code in ("sales_head", "sales_team_leader", "sales_member"):
            cur.execute("SELECT id FROM rbac_role WHERE code = %s", (code,))
            self.roles[code] = cur.fetchone()["id"]

        cur.execute("SELECT id FROM client ORDER BY id LIMIT 1")
        client_id = cur.fetchone()["id"]

        # head -> leader -> two members, all in the same department.
        self.head, self.leader, self.member_a, self.member_b = (
            self._make_user("scope-head", "sales_head", None),
            None, None, None,
        )
        self.leader = self._make_user("scope-leader", "sales_team_leader", self.head)
        self.member_a = self._make_user("scope-member-a", "sales_member", self.leader)
        self.member_b = self._make_user("scope-member-b", "sales_member", self.leader)
        # An outsider in no department, to prove department scope is a real bound.
        self.outsider = self._make_user("scope-outsider", "sales_member", None, department=False)

        self.requests = {}
        for owner in (self.head, self.leader, self.member_a, self.member_b, self.outsider):
            cur.execute(
                """
                INSERT INTO sales_request (client_id, title, start_date, created_by,
                                           items_count, owner_user_id)
                VALUES (%s, 'Scope test request', CURDATE(), 'scope-test', 0, %s)
                """,
                (client_id, owner),
            )
            self.requests[owner] = cur.lastrowid
        cur.close()

    def tearDown(self):
        branding_gate.connection = self.original_connection
        self.raw_connection.rollback()
        self.raw_connection.close()

    def _cursor(self):
        return self.raw_connection.cursor(MySQLdb.cursors.DictCursor)

    def _connection(self):
        return self.wrapper, self._cursor()

    def _make_user(self, username, role_code, manager_id, department=True):
        cur = self._cursor()
        cur.execute(
            """
            INSERT INTO user (name, mobile, email, password, username, title,
                              department_id, rbac_role_id, manager_id, date)
            VALUES (%s, %s, %s, 'x', %s, 'Scope Test', %s, %s, %s, NOW())
            """,
            (username, '019%08d' % (abs(hash(username)) % 10**8), username + '@example.com',
             username, self.department_id if department else None,
             self.roles[role_code], manager_id),
        )
        user_id = cur.lastrowid
        cur.close()
        return user_id

    def _requests_visible_to(self, user_id):
        perms, role_code = branding_gate.load_permissions(user_id)
        client = branding_gate.app.test_client()
        with client.session_transaction() as flask_session:
            flask_session.update({
                "user_id": user_id, "mobile": "m", "email": "e",
                "username": "u", "name": "n",
                "roles": [role_code], "perms": perms, "role_code": role_code,
            })
        response = client.get('/api/sales/requests')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        rows = payload.get('requests') or payload.get('data') or []
        # The list endpoint exposes the primary key as request_id.
        ours = set(self.requests.values())
        return {row['request_id'] for row in rows if row.get('request_id') in ours}

    def test_a_member_sees_only_their_own_requests(self):
        self.assertEqual(
            self._requests_visible_to(self.member_a),
            {self.requests[self.member_a]},
        )

    def test_a_team_leader_sees_their_reports(self):
        self.assertEqual(
            self._requests_visible_to(self.leader),
            {self.requests[self.leader], self.requests[self.member_a], self.requests[self.member_b]},
        )

    def test_a_head_sees_the_whole_department_but_not_outsiders(self):
        visible = self._requests_visible_to(self.head)
        self.assertEqual(
            visible,
            {self.requests[self.head], self.requests[self.leader],
             self.requests[self.member_a], self.requests[self.member_b]},
        )
        self.assertNotIn(self.requests[self.outsider], visible)

    def test_a_member_cannot_open_another_members_request_by_id(self):
        perms, role_code = branding_gate.load_permissions(self.member_a)
        client = branding_gate.app.test_client()
        with client.session_transaction() as flask_session:
            flask_session.update({
                "user_id": self.member_a, "mobile": "m", "email": "e",
                "username": "u", "name": "n",
                "roles": [role_code], "perms": perms, "role_code": role_code,
            })
        own = client.get('/api/sales/requests/%d' % self.requests[self.member_a])
        other = client.get('/api/sales/requests/%d' % self.requests[self.member_b])
        self.assertEqual(own.status_code, 200)
        self.assertEqual(other.status_code, 403)

    def test_visible_user_ids_matches_the_hierarchy(self):
        with branding_gate.app.test_request_context('/'):
            branding_gate.session['user_id'] = self.leader
            branding_gate.session['perms'] = {'sales_request.view': 'team'}
            self.assertEqual(
                set(branding_gate.visible_user_ids('sales_request.view')),
                {self.leader, self.member_a, self.member_b},
            )
            branding_gate.session['perms'] = {'sales_request.view': 'all'}
            self.assertIsNone(branding_gate.visible_user_ids('sales_request.view'))
            branding_gate.session['perms'] = {'sales_request.view': 'own'}
            self.assertEqual(branding_gate.visible_user_ids('sales_request.view'), [self.leader])


class ScopeClauseTest(unittest.TestCase):
    """scope_clause must never degrade to 'show everything'."""

    def test_unrestricted_scope_produces_no_predicate(self):
        with branding_gate.app.test_request_context('/'):
            branding_gate.session['user_id'] = 1
            branding_gate.session['perms'] = {'sales_request.view': 'all'}
            self.assertEqual(
                branding_gate.scope_clause('sales_request.view', 'sr.owner_user_id'),
                ("", []),
            )

    def test_own_scope_binds_the_caller(self):
        with branding_gate.app.test_request_context('/'):
            branding_gate.session['user_id'] = 42
            branding_gate.session['perms'] = {'sales_request.view': 'own'}
            clause, params = branding_gate.scope_clause('sales_request.view', 'sr.owner_user_id')
            self.assertEqual(clause, " AND sr.owner_user_id IN (%s)")
            self.assertEqual(params, [42])

    def test_a_missing_permission_aborts_rather_than_returning_everything(self):
        with branding_gate.app.test_request_context('/'):
            branding_gate.session['user_id'] = 42
            branding_gate.session['perms'] = {}
            with self.assertRaises(Exception):
                branding_gate.scope_clause('sales_request.view', 'sr.owner_user_id')


if __name__ == '__main__':
    unittest.main()
