"""
Recording the client's answer on the Client Approval page.

The account manager is the one in the room when the client says yes, no, or
"cheaper" -- and the page offered them Approve, Reject and Negotiate, then
refused all three: `client_approval.decide` was held by the account director
and the sales head only, so every press came back 403 and the page said
"Failed to approve item". Sarah Gaber, an account team leader, hit it five
times on one item.

Two halves. The account roles now hold the permission -- a member for their
own requests, a leader for their team's. And the decide routes now apply the
scope the list already applies: before this they checked the permission and
nothing else, so anyone holding it at any scope could act on any item by id.

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


class AccountRolesMayDecideTest(unittest.TestCase):

    def test_the_account_line_holds_the_permission_within_its_scope(self):
        matrix = rbac.SEED_MATRIX
        self.assertEqual(matrix['account_director'].get('client_approval.decide'), 'department')
        self.assertEqual(matrix['account_team_leader'].get('client_approval.decide'), 'team')
        self.assertEqual(matrix['account_member'].get('client_approval.decide'), 'own')


class DecideRoutesTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4",
                                   use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self._cursor())
        branding_gate.app.config['TESTING'] = True
        self._real_notify = branding_gate.notify_users
        branding_gate.notify_users = lambda ids, title, body, link=None: len(ids or [])

        cur = self._cursor()
        cur.execute("SELECT id FROM department ORDER BY id LIMIT 1")
        self.department = cur.fetchone()['id']
        self.roles = {}
        for code in ('account_team_leader', 'account_member', 'sales_member'):
            cur.execute("SELECT id FROM rbac_role WHERE code = %s", (code,))
            self.roles[code] = cur.fetchone()['id']
        # The grants as rbac.py now defines them, written inside this
        # transaction: the test must not depend on whether seed_rbac.py has
        # been run against this database yet.
        for code in ('account_team_leader', 'account_member'):
            cur.execute("""INSERT INTO role_permission (role_id, permission_code, scope)
                           VALUES (%s, 'client_approval.decide', %s)
                           ON DUPLICATE KEY UPDATE scope = VALUES(scope)""",
                        (self.roles[code], rbac.SEED_MATRIX[code]['client_approval.decide']))
        cur.close()

        # Two teams: a leader with one member each.
        self.leader = self._make_user('decide-leader', 'account_team_leader')
        self.member = self._make_user('decide-member', 'account_member', manager=self.leader)
        self.teammate = self._make_user('decide-teammate', 'account_member', manager=self.leader)
        self.other_leader = self._make_user('decide-leader-2', 'account_team_leader')
        self.salesperson = self._make_user('decide-sales', 'sales_member', manager=self.leader)

        self.item = self._priced_item(owner=self.member)

    def tearDown(self):
        branding_gate.notify_users = self._real_notify
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _make_user(self, username, role_code, manager=None):
        cur = self._cursor()
        cur.execute("""INSERT INTO user (name, mobile, email, password, username, title,
                                         department_id, rbac_role_id, manager_id, date)
                       VALUES (%s, %s, %s, 'x', %s, 'Decide Test', %s, %s, %s, NOW())""",
                    (username, '016%08d' % (abs(hash(username)) % 10 ** 8),
                     username + '@example.com', username,
                     self.department, self.roles[role_code], manager))
        user_id = cur.lastrowid
        cur.close()
        return user_id

    def _priced_item(self, owner):
        cur = self._cursor()
        client_id = fixtures.ensure_client(cur)
        cur.execute("""INSERT INTO sales_request (client_id, title, start_date, created_by,
                                                  items_count, owner_user_id)
                       VALUES (%s, 'Decide test request', CURDATE(), 'decide-test', 1, %s)""",
                    (client_id, owner))
        request_id = cur.lastrowid
        cur.execute("""INSERT INTO sales_request_items
                           (request_id, name, qty, cost_per_item, sell_per_item,
                            total_cost, total_sell, approval_status)
                       VALUES (%s, 'Decide item', 10, 80, 120, 800, 1200, 'pending')""",
                    (request_id,))
        item_id = cur.lastrowid
        cur.close()
        return item_id

    def _client_for(self, user_id):
        perms, role_code = branding_gate.load_permissions(user_id)
        client = branding_gate.app.test_client()
        with client.session_transaction() as flask_session:
            flask_session.update({'user_id': user_id, 'mobile': 'm', 'email': 'e',
                                  'username': 'u', 'name': 'Decider', 'roles': [role_code],
                                  'perms': perms, 'role_code': role_code})
        return client

    def _status(self, item_id):
        cur = self._cursor()
        cur.execute("SELECT approval_status FROM sales_request_items WHERE id = %s", (item_id,))
        status = cur.fetchone()['approval_status']
        cur.close()
        return status

    def _approve(self, user_id, item_id=None):
        return self._client_for(user_id).post(
            '/api/client-approval/items/%d/approve' % (item_id or self.item),
            json={'approved': True})

    # --- inside their scope ------------------------------------------------

    def test_a_member_records_the_answer_on_their_own_request(self):
        response = self._approve(self.member)
        self.assertEqual(response.status_code, 200, response.data[:300])
        self.assertEqual(self._status(self.item), 'approved')

    def test_a_leader_records_it_on_their_teams_request(self):
        response = self._approve(self.leader)
        self.assertEqual(response.status_code, 200, response.data[:300])
        self.assertEqual(self._status(self.item), 'approved')

    def test_a_leader_can_reject_and_negotiate_too(self):
        leader = self._client_for(self.leader)
        rejected = leader.post('/api/client-approval/items/%d/reject' % self.item,
                               json={'rejected': True, 'reason': 'Too dear'})
        self.assertEqual(rejected.status_code, 200, rejected.data[:300])

        second = self._priced_item(owner=self.member)
        negotiated = leader.post('/api/client-approval/items/%d/negotiate' % second,
                                 json={'reason': 'Client wants 100', 'expected_price': 100})
        self.assertEqual(negotiated.status_code, 200, negotiated.data[:300])

    # --- outside it ---------------------------------------------------------

    def test_a_member_cannot_decide_on_a_teammates_request(self):
        theirs = self._priced_item(owner=self.teammate)
        response = self._approve(self.member, theirs)
        self.assertEqual(response.status_code, 403)
        self.assertIn('outside the ones you look after', response.get_json()['error'])
        self.assertEqual(self._status(theirs), 'pending', 'the refused approval still landed')

    def test_a_leader_cannot_decide_on_another_teams_request(self):
        for route, body in (('approve', {'approved': True}),
                            ('reject', {'rejected': True, 'reason': 'x'}),
                            ('negotiate', {'reason': 'x', 'expected_price': 90})):
            response = self._client_for(self.other_leader).post(
                '/api/client-approval/items/%d/%s' % (self.item, route), json=body)
            self.assertEqual(response.status_code, 403, route)
        self.assertEqual(self._status(self.item), 'pending')

    def test_sales_members_are_unchanged(self):
        # Only the account line was granted; sales members still may not.
        response = self._approve(self.salesperson)
        self.assertEqual(response.status_code, 403)

    def test_a_missing_item_is_still_a_404(self):
        response = self._approve(self.leader, 999999999)
        self.assertEqual(response.status_code, 404)

    # --- the change log ----------------------------------------------------

    def test_a_negotiation_reaches_the_activity_flow(self):
        # The negotiate route hands log_item_change the item's prices as MySQL
        # returns them -- Decimal -- and json.dumps refused them. The function
        # caught that, printed it, and dropped the entry.
        import contextlib
        import decimal
        import io
        out = io.StringIO()
        cur = self._cursor()
        cur.execute("SELECT request_id FROM sales_request_items WHERE id = %s", (self.item,))
        request_id = cur.fetchone()['request_id']
        with contextlib.redirect_stdout(out):
            branding_gate.log_item_change(
                request_id=request_id, item_id=self.item, item_name='Decide item',
                request_type='General', action_type='CLIENT_NEGOTIATION', action_by='Decider',
                old_data={'cost': decimal.Decimal('80.00'), 'sell': decimal.Decimal('120.00')},
                new_data={'status': 'pending_negotiation', 'expected_price': 100.0},
                change_description='negotiation', conn=_RollbackConnection(self.raw), cur=cur)
        cur.close()
        printed = out.getvalue()
        self.assertNotIn('Failed to log item change', printed)
        self.assertIn('Logged item change', printed)

    # --- the page -----------------------------------------------------------

    def test_the_page_says_why_it_failed(self):
        with open('templates/client_approval.html', encoding='utf-8') as handle:
            page = handle.read()
        self.assertNotIn("Swal.fire('Error', 'Failed to approve item', 'error');", page)
        self.assertIn('function decideError(', page)

    def test_the_page_only_offers_the_buttons_to_whoever_may_press_them(self):
        with open('templates/client_approval.html', encoding='utf-8') as handle:
            page = handle.read()
        self.assertIn("{{ ('client_approval.decide' in _p)|tojson }}", page)
        self.assertIn('CAN_DECIDE', page)


if __name__ == '__main__':
    unittest.main()
