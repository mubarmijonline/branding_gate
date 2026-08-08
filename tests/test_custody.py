"""
عهدة: the layer above signs, then Finance, then the money moves.

Rollback-based, like tests/test_costing.py: every test builds its own people and
rows inside a transaction that is rolled back, so nothing survives the run.
"""

import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate
import rbac


class _RollbackConnection:
    """
    Transaction control belongs to the test, not to the code under test.

    Both commit and rollback are swallowed. A route that refuses a request rolls
    back to release the rows it locked, which is right in production and would
    otherwise throw away the people and rows this test set up.
    """

    def __init__(self, raw_connection):
        self.raw_connection = raw_connection

    def commit(self):
        pass

    def close(self):
        pass

    def rollback(self):
        pass


class CustodyFlowTest(unittest.TestCase):
    """Member -> their manager -> Finance -> عهدة."""

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
        for code in ('sales_head', 'sales_team_leader', 'sales_member', 'finance_manager'):
            cur.execute("SELECT id FROM rbac_role WHERE code = %s", (code,))
            self.roles[code] = cur.fetchone()["id"]

        # The tree this flow is decided by: CEO -> head -> leader -> member.
        self.ceo = self._make_user('custody-ceo', 'sales_head', None)
        self.head = self._make_user('custody-head', 'sales_head', self.ceo)
        self.leader = self._make_user('custody-leader', 'sales_team_leader', self.head)
        self.member = self._make_user('custody-member', 'sales_member', self.leader)
        self.other_leader = self._make_user('custody-other-leader', 'sales_team_leader', self.head)
        self.finance = self._make_user('custody-finance', 'finance_manager', self.ceo)
        cur.close()

    def tearDown(self):
        branding_gate.connection = self.original_connection
        self.raw_connection.rollback()
        self.raw_connection.close()

    def _cursor(self):
        return self.raw_connection.cursor(MySQLdb.cursors.DictCursor)

    def _connection(self):
        return self.wrapper, self._cursor()

    def _make_user(self, username, role_code, manager_id):
        cur = self._cursor()
        cur.execute(
            """
            INSERT INTO user (name, mobile, email, password, username, title,
                              department_id, rbac_role_id, manager_id, date)
            VALUES (%s, %s, %s, 'x', %s, 'Custody Test', %s, %s, %s, NOW())
            """,
            (username, '018%08d' % (abs(hash(username)) % 10**8),
             username + '@example.com', username, self.department_id,
             self.roles[role_code], manager_id),
        )
        user_id = cur.lastrowid
        cur.close()
        return user_id

    def _client_for(self, user_id):
        perms, role_code = branding_gate.load_permissions(user_id)
        client = branding_gate.app.test_client()
        with client.session_transaction() as flask_session:
            flask_session.update({
                "user_id": user_id, "mobile": "m", "email": "e",
                "username": "u", "name": "n",
                "roles": [role_code], "perms": perms, "role_code": role_code,
            })
        return client

    def _request_balance(self, actor, amount=500, reason='fuel'):
        return self._client_for(actor).post('/api/finance/request-balance',
                                            json={'amount': amount, 'description': reason})

    def _row(self, request_id):
        cur = self._cursor()
        cur.execute("SELECT * FROM user_balance_transfers WHERE id = %s", (request_id,))
        row = cur.fetchone()
        cur.close()
        return row

    def _latest_for(self, user_id):
        cur = self._cursor()
        cur.execute("""
            SELECT * FROM user_balance_transfers
            WHERE to_user_id = %s ORDER BY id DESC LIMIT 1
        """, (user_id,))
        row = cur.fetchone()
        cur.close()
        return row

    # -- who signs ----------------------------------------------------------

    def test_a_member_waits_on_their_own_manager(self):
        response = self._request_balance(self.member)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['status'], 'pending_manager')
        self.assertEqual(self._latest_for(self.member)['status'], 'pending_manager')

    def test_somebody_reporting_to_the_ceo_goes_straight_to_finance(self):
        # The head's manager is the root of the tree, so there is no layer in
        # between to sign.
        response = self._request_balance(self.head)
        self.assertEqual(response.get_json()['status'], 'pending_finance')

    def test_the_root_of_the_tree_goes_straight_to_finance(self):
        response = self._request_balance(self.ceo)
        self.assertEqual(response.get_json()['status'], 'pending_finance')

    def test_only_their_own_manager_may_sign(self):
        self._request_balance(self.member)
        request_id = self._latest_for(self.member)['id']
        # A team leader in the same department, but not theirs.
        refused = self._client_for(self.other_leader).post(
            '/api/finance/balance-requests/%d/manager-approve' % request_id, json={})
        self.assertEqual(refused.status_code, 403)
        self.assertEqual(self._row(request_id)['status'], 'pending_manager')

        allowed = self._client_for(self.leader).post(
            '/api/finance/balance-requests/%d/manager-approve' % request_id, json={})
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(self._row(request_id)['status'], 'pending_finance')

    def test_finance_cannot_pay_what_the_manager_has_not_signed(self):
        self._request_balance(self.member)
        request_id = self._latest_for(self.member)['id']
        cur = self._cursor()
        cur.execute("SELECT id FROM payment_methods LIMIT 1")
        payment_method = cur.fetchone()
        cur.close()
        if not payment_method:
            self.skipTest('no payment method in this database')
        response = self._client_for(self.finance).post(
            '/api/finance/balance-requests/%d/approve' % request_id,
            json={'payment_method_id': payment_method['id']})
        self.assertEqual(response.status_code, 404)

    # -- the manager's pencil ----------------------------------------------

    def test_a_manager_may_correct_the_amount_and_the_original_survives(self):
        self._request_balance(self.member, amount=500)
        request_id = self._latest_for(self.member)['id']
        response = self._client_for(self.leader).post(
            '/api/finance/balance-requests/%d/manager-approve' % request_id,
            json={'amount': 300, 'notes': 'half the trip is covered'})
        self.assertEqual(response.status_code, 200)
        row = self._row(request_id)
        self.assertEqual(float(row['amount']), 300.0)
        self.assertEqual(float(row['original_amount']), 500.0)
        self.assertEqual(row['manager_approved_by'], self.leader)

    def test_a_manager_may_refuse_but_must_say_why(self):
        self._request_balance(self.member)
        request_id = self._latest_for(self.member)['id']
        silent = self._client_for(self.leader).post(
            '/api/finance/balance-requests/%d/manager-reject' % request_id, json={})
        self.assertEqual(silent.status_code, 400)

        spoken = self._client_for(self.leader).post(
            '/api/finance/balance-requests/%d/manager-reject' % request_id,
            json={'reason': 'buy it from the office float'})
        self.assertEqual(spoken.status_code, 200)
        row = self._row(request_id)
        self.assertEqual(row['status'], 'rejected')
        self.assertEqual(row['rejection_reason'], 'buy it from the office float')

    def test_the_requester_may_withdraw_while_anybody_still_holds_it(self):
        self._request_balance(self.member)
        request_id = self._latest_for(self.member)['id']
        response = self._client_for(self.member).post(
            '/api/finance/balance-requests/%d/cancel' % request_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._row(request_id)['status'], 'cancelled')

    def test_one_person_cannot_withdraw_another_persons_request(self):
        self._request_balance(self.member)
        request_id = self._latest_for(self.member)['id']
        response = self._client_for(self.other_leader).post(
            '/api/finance/balance-requests/%d/cancel' % request_id)
        self.assertEqual(response.status_code, 404)

    # -- the manager's queue -------------------------------------------------

    def test_the_queue_shows_a_manager_their_own_reports_only(self):
        self._request_balance(self.member)
        mine = self._client_for(self.leader).get(
            '/api/finance/balance-requests/waiting-on-me').get_json()
        self.assertEqual([r['to_user_id'] for r in mine['requests']], [self.member])

        theirs = self._client_for(self.other_leader).get(
            '/api/finance/balance-requests/waiting-on-me').get_json()
        self.assertEqual(theirs['requests'], [])


class CustodySettlementTest(CustodyFlowTest):
    """تسوية عهدة: handing back what is left."""

    def _give_balance(self, user_id, amount):
        cur = self._cursor()
        cur.execute("""
            INSERT INTO user_finance_balances (user_id, balance) VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE balance = %s
        """, (user_id, amount, amount))
        cur.close()

    def test_you_cannot_hand_back_more_than_you_hold(self):
        self._give_balance(self.member, 100)
        response = self._client_for(self.member).post(
            '/api/finance/custody/settle', json={'amount': 250})
        self.assertEqual(response.status_code, 400)
        self.assertIn('more than you hold', response.get_json()['error'])

    def test_a_settlement_moves_nothing_until_finance_confirms(self):
        self._give_balance(self.member, 400)
        response = self._client_for(self.member).post(
            '/api/finance/custody/settle', json={'amount': 150})
        self.assertEqual(response.status_code, 200)

        cur = self._cursor()
        cur.execute("SELECT balance FROM user_finance_balances WHERE user_id = %s", (self.member,))
        self.assertEqual(float(cur.fetchone()['balance']), 400.0)
        cur.execute("""
            SELECT status, transfer_type FROM user_balance_transfers
            WHERE requested_by = %s ORDER BY id DESC LIMIT 1
        """, (self.member,))
        row = cur.fetchone()
        cur.close()
        self.assertEqual((row['status'], row['transfer_type']),
                         ('pending_finance', 'settlement'))

    def test_confirming_it_lowers_the_custody_and_raises_the_payment_method(self):
        cur = self._cursor()
        cur.execute("SELECT id, current_balance FROM payment_methods LIMIT 1")
        payment_method = cur.fetchone()
        cur.close()
        if not payment_method:
            self.skipTest('no payment method in this database')

        self._give_balance(self.member, 400)
        self._client_for(self.member).post('/api/finance/custody/settle', json={'amount': 150})
        cur = self._cursor()
        cur.execute("""
            SELECT id FROM user_balance_transfers
            WHERE requested_by = %s AND transfer_type = 'settlement' ORDER BY id DESC LIMIT 1
        """, (self.member,))
        settlement_id = cur.fetchone()['id']
        cur.close()

        response = self._client_for(self.finance).post(
            '/api/finance/custody/settlements/%d/confirm' % settlement_id,
            json={'payment_method_id': payment_method['id']})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['new_balance'], 250.0)

        cur = self._cursor()
        cur.execute("SELECT balance FROM user_finance_balances WHERE user_id = %s", (self.member,))
        self.assertEqual(float(cur.fetchone()['balance']), 250.0)
        cur.execute("SELECT current_balance FROM payment_methods WHERE id = %s",
                    (payment_method['id'],))
        self.assertEqual(float(cur.fetchone()['current_balance']),
                         float(payment_method['current_balance']) + 150.0)
        cur.execute("""
            SELECT change_type, change_amount FROM user_balance_history
            WHERE user_id = %s ORDER BY id DESC LIMIT 1
        """, (self.member,))
        history = cur.fetchone()
        cur.close()
        self.assertEqual(history['change_type'], 'settlement')
        self.assertEqual(float(history['change_amount']), -150.0)


class ExpenseSalesRequestTest(CustodyFlowTest):
    """Every expense line names the work it was spent on."""

    def _submit(self, actor, items):
        return self._client_for(actor).post('/api/expense-tracking', json={
            'items': items, 'description': 'test sheet',
            'tracking_date': '2026-08-08'})

    def _a_sales_request(self):
        cur = self._cursor()
        cur.execute("SELECT id FROM sales_request ORDER BY id LIMIT 1")
        row = cur.fetchone()
        cur.close()
        return row['id'] if row else None

    def test_a_line_without_a_sales_request_is_refused(self):
        response = self._submit(self.member, [{'description': 'taxi', 'amount': 50}])
        self.assertEqual(response.status_code, 400)
        self.assertIn('sales request', response.get_json()['error'].lower())

    def test_a_sales_request_that_does_not_exist_is_refused(self):
        response = self._submit(self.member, [
            {'description': 'taxi', 'amount': 50, 'sales_request_id': 99999999}])
        self.assertEqual(response.status_code, 400)
        self.assertIn('No such sales request', response.get_json()['error'])

    def test_a_good_line_is_kept_with_its_request(self):
        request_id = self._a_sales_request()
        if not request_id:
            self.skipTest('no sales request in this database')
        response = self._submit(self.member, [
            {'description': 'taxi', 'amount': 50, 'sales_request_id': request_id}])
        self.assertEqual(response.status_code, 200, response.get_json())
        tracking_id = response.get_json()['tracking_id']

        cur = self._cursor()
        cur.execute("""
            SELECT sales_request_id, amount FROM expense_tracking_items WHERE tracking_id = %s
        """, (tracking_id,))
        rows = cur.fetchall()
        cur.close()
        self.assertEqual([r['sales_request_id'] for r in rows], [request_id])

    def test_only_their_own_manager_may_approve_the_sheet(self):
        request_id = self._a_sales_request()
        if not request_id:
            self.skipTest('no sales request in this database')
        tracking_id = self._submit(self.member, [
            {'description': 'taxi', 'amount': 50, 'sales_request_id': request_id}
        ]).get_json()['tracking_id']

        refused = self._client_for(self.other_leader).post(
            '/api/expense-tracking/%d/manager-approve' % tracking_id, json={})
        self.assertEqual(refused.status_code, 403)

        allowed = self._client_for(self.leader).post(
            '/api/expense-tracking/%d/manager-approve' % tracking_id, json={})
        self.assertEqual(allowed.status_code, 200)

    def test_a_manager_correcting_a_line_keeps_what_was_claimed(self):
        request_id = self._a_sales_request()
        if not request_id:
            self.skipTest('no sales request in this database')
        tracking_id = self._submit(self.member, [
            {'description': 'taxi', 'amount': 50, 'sales_request_id': request_id}
        ]).get_json()['tracking_id']

        cur = self._cursor()
        cur.execute("SELECT id FROM expense_tracking_items WHERE tracking_id = %s", (tracking_id,))
        item_id = cur.fetchone()['id']
        cur.close()

        response = self._client_for(self.leader).post(
            '/api/expense-tracking/%d/update-items' % tracking_id,
            json={'items': [{'id': item_id, 'amount': 30}]})
        self.assertEqual(response.status_code, 200, response.get_json())

        cur = self._cursor()
        cur.execute("SELECT amount, original_amount FROM expense_tracking_items WHERE id = %s",
                    (item_id,))
        row = cur.fetchone()
        cur.execute("SELECT total_amount FROM expense_tracking WHERE id = %s", (tracking_id,))
        header = cur.fetchone()
        cur.close()
        self.assertEqual(float(row['amount']), 30.0)
        self.assertEqual(float(row['original_amount']), 50.0)
        self.assertEqual(float(header['total_amount']), 30.0)

    def test_a_stranger_may_not_change_the_amounts(self):
        request_id = self._a_sales_request()
        if not request_id:
            self.skipTest('no sales request in this database')
        tracking_id = self._submit(self.member, [
            {'description': 'taxi', 'amount': 50, 'sales_request_id': request_id}
        ]).get_json()['tracking_id']
        cur = self._cursor()
        cur.execute("SELECT id FROM expense_tracking_items WHERE tracking_id = %s", (tracking_id,))
        item_id = cur.fetchone()['id']
        cur.close()

        response = self._client_for(self.other_leader).post(
            '/api/expense-tracking/%d/update-items' % tracking_id,
            json={'items': [{'id': item_id, 'amount': 5}]})
        self.assertEqual(response.status_code, 403)


class CustodyPolicyTest(unittest.TestCase):
    """The grants, without a database."""

    def test_every_leader_signs_for_their_own_team(self):
        for role in ('sales_head', 'sales_team_leader', 'operations_manager',
                     'account_team_leader', 'finance_manager'):
            self.assertEqual(rbac.SEED_MATRIX[role].get('user_balance.approve_manager'),
                             'team', role)

    def test_a_member_signs_for_nobody(self):
        for role in ('sales_member', 'operations_member', 'marketing_member',
                     'pricing_specialist'):
            self.assertNotIn('user_balance.approve_manager', rbac.SEED_MATRIX[role], role)

    def test_the_assistant_stays_out_of_it(self):
        # A head by level, with nobody under them and no approvals of any kind.
        self.assertNotIn('user_balance.approve_manager', rbac.SEED_MATRIX['assistant'])

    def test_everybody_can_hand_back_their_own_عهدة(self):
        for role in rbac.ROLES:
            self.assertIn('user_balance.settle', rbac.SEED_MATRIX[role], role)


if __name__ == '__main__':
    unittest.main()
