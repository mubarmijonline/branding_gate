"""
Asking for a client or a supplier: the team asks, their head passes, an admin
adds it. Rollback-based, like the other route tests here.
"""

import json
import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate
import rbac


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def close(self): pass
    def rollback(self): pass


class PartyRequestFlowTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self._cursor())

        cur = self._cursor()
        self.departments, self.roles = {}, {}
        for code in ('operations', 'sales', 'account'):
            cur.execute("SELECT id FROM department WHERE code = %s", (code,))
            self.departments[code] = cur.fetchone()['id']
        for code in ('operations_manager', 'operations_member', 'sales_head',
                     'sales_member', 'account_director', 'admin'):
            cur.execute("SELECT id FROM rbac_role WHERE code = %s", (code,))
            self.roles[code] = cur.fetchone()['id']

        self.ops_head = self._user('pr-ops-head', 'operations_manager', 'operations')
        self.ops_member = self._user('pr-ops-member', 'operations_member', 'operations')
        self.sales_head = self._user('pr-sales-head', 'sales_head', 'sales')
        self.sales_member = self._user('pr-sales-member', 'sales_member', 'sales')
        self.admin = self._user('pr-admin', 'admin', 'operations')
        cur.close()

    def tearDown(self):
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _user(self, username, role_code, dept):
        cur = self._cursor()
        cur.execute("""INSERT INTO user (name, mobile, email, password, username, title,
                                         department_id, rbac_role_id, date)
                       VALUES (%s, %s, %s, 'x', %s, 'Party Test', %s, %s, NOW())""",
                    (username, '017%08d' % (abs(hash(username)) % 10**8),
                     username + '@example.com', username,
                     self.departments[dept], self.roles[role_code]))
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

    def _ask_supplier(self, actor, name='Test Supplier'):
        return self._client_for(actor).post('/api/party-requests', json={
            'kind': 'supplier', 'supplier_name': name,
            'email_address': 'a@b.example', 'primary_phone': '0100'})

    def _latest(self):
        cur = self._cursor()
        cur.execute("SELECT * FROM party_request ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        cur.close()
        return row

    # -- raising -------------------------------------------------------------

    def test_an_operations_member_may_ask_for_a_supplier(self):
        response = self._ask_supplier(self.ops_member)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self._latest()['status'], 'pending_head')

    def test_sales_may_not_ask_for_a_supplier(self):
        response = self._ask_supplier(self.sales_member)
        self.assertEqual(response.status_code, 403)

    def test_operations_may_not_ask_for_a_client(self):
        response = self._client_for(self.ops_member).post('/api/party-requests', json={
            'kind': 'client', 'client_name': 'X', 'mobile_number': '1', 'email_address': 'a@b.c'})
        self.assertEqual(response.status_code, 403)

    def test_the_required_fields_are_required(self):
        response = self._client_for(self.ops_member).post('/api/party-requests',
                                                          json={'kind': 'supplier'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('supplier name', response.get_json()['error'])

    # -- passing -------------------------------------------------------------

    def test_only_that_departments_head_may_approve_it(self):
        self._ask_supplier(self.ops_member)
        request_id = self._latest()['id']
        outsider = self._client_for(self.sales_head).post(
            '/api/party-requests/%d/head-approve' % request_id, json={})
        self.assertEqual(outsider.status_code, 403)
        theirs = self._client_for(self.ops_head).post(
            '/api/party-requests/%d/head-approve' % request_id, json={})
        self.assertEqual(theirs.status_code, 200, theirs.get_json())
        self.assertEqual(self._latest()['status'], 'approved')

    def test_the_head_adds_it_without_waiting_for_an_admin(self):
        # The admin step was removed: the head knows the supplier, and a second
        # desk added delay without adding judgement.
        self._ask_supplier(self.ops_member, name='Added By The Head')
        request_id = self._latest()['id']
        response = self._client_for(self.ops_head).post(
            '/api/party-requests/%d/head-approve' % request_id, json={})
        self.assertEqual(response.status_code, 200, response.get_json())

        cur = self._cursor()
        cur.execute("SELECT id FROM supplier WHERE supplier_name = 'Added By The Head'")
        row = cur.fetchone()
        cur.close()
        self.assertIsNotNone(row, 'the head approving is what adds it')
        self.assertEqual(self._latest()['created_record_id'], row['id'])

    def test_asking_alone_creates_nothing(self):
        self._ask_supplier(self.ops_member, name='Only Asked For')
        cur = self._cursor()
        cur.execute("SELECT COUNT(*) AS n FROM supplier WHERE supplier_name = 'Only Asked For'")
        self.assertEqual(cur.fetchone()['n'], 0, 'a request must not create the row')
        cur.close()

    def test_an_admin_may_still_finish_one_left_mid_flight(self):
        # Nothing routes to the admin any more, but a request raised before that
        # changed must not be stranded.
        self._ask_supplier(self.ops_member, name='Left Mid Flight')
        request_id = self._latest()['id']
        cur = self._cursor()
        cur.execute("UPDATE party_request SET status = 'pending_admin' WHERE id = %s",
                    (request_id,))
        cur.close()
        response = self._client_for(self.admin).post(
            '/api/party-requests/%d/approve' % request_id, json={})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self._latest()['status'], 'approved')

    def test_declining_needs_a_reason_and_the_requester_can_read_it(self):
        self._ask_supplier(self.ops_member)
        request_id = self._latest()['id']
        silent = self._client_for(self.ops_head).post(
            '/api/party-requests/%d/reject' % request_id, json={})
        self.assertEqual(silent.status_code, 400)
        spoken = self._client_for(self.ops_head).post(
            '/api/party-requests/%d/reject' % request_id, json={'reason': 'we already use one'})
        self.assertEqual(spoken.status_code, 200)
        row = self._latest()
        self.assertEqual((row['status'], row['rejection_reason']),
                         ('rejected', 'we already use one'))

    def test_the_requester_may_withdraw_their_own(self):
        self._ask_supplier(self.ops_member)
        request_id = self._latest()['id']
        other = self._client_for(self.sales_member).post(
            '/api/party-requests/%d/cancel' % request_id)
        self.assertEqual(other.status_code, 404)
        mine = self._client_for(self.ops_member).post(
            '/api/party-requests/%d/cancel' % request_id)
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(self._latest()['status'], 'cancelled')

    # -- who sees what -------------------------------------------------------

    def test_a_member_sees_their_own_and_a_head_sees_the_department(self):
        self._ask_supplier(self.ops_member)
        mine = self._client_for(self.ops_member).get('/api/party-requests').get_json()
        self.assertEqual(len(mine['requests']), 1)
        self.assertFalse(mine['requests'][0]['can_pass'])

        head = self._client_for(self.ops_head).get('/api/party-requests').get_json()
        self.assertTrue(any(r['can_pass'] for r in head['requests']))

        stranger = self._client_for(self.sales_member).get('/api/party-requests').get_json()
        self.assertEqual(stranger['requests'], [])

    def test_the_payload_reaches_the_approver_in_full(self):
        self._client_for(self.ops_member).post('/api/party-requests', json={
            'kind': 'supplier', 'supplier_name': 'Full Detail', 'email_address': 'a@b.example',
            'primary_phone': '0111', 'address': 'Somewhere', 'website': 'example.com'})
        head = self._client_for(self.ops_head).get('/api/party-requests').get_json()
        payload = head['requests'][0]['payload']
        self.assertEqual(payload['supplier_name'], 'Full Detail')
        self.assertEqual(payload['address'], 'Somewhere')
        self.assertEqual(payload['website'], 'example.com')


class PartyRequestPolicyTest(unittest.TestCase):

    def test_clients_are_asked_for_by_sales_and_account(self):
        holders = {r for r, g in rbac.SEED_MATRIX.items() if 'client_request.create' in g}
        self.assertTrue({'sales_member', 'sales_head', 'account_member',
                         'account_director'} <= holders)
        self.assertNotIn('operations_member', holders)

    def test_suppliers_are_asked_for_by_operations_and_purchasing(self):
        holders = {r for r, g in rbac.SEED_MATRIX.items() if 'supplier_request.create' in g}
        self.assertTrue({'operations_member', 'operations_manager',
                         'design_3d_purchasing'} <= holders)
        self.assertNotIn('sales_member', holders)

    def test_only_heads_pass_and_only_admin_finalises(self):
        heads = {r for r, g in rbac.SEED_MATRIX.items() if 'party_request.approve_head' in g}
        self.assertTrue({'sales_head', 'account_director', 'operations_manager'} <= heads)
        self.assertNotIn('sales_member', heads)
        finalisers = {r for r, g in rbac.SEED_MATRIX.items() if 'party_request.approve_admin' in g}
        self.assertEqual(finalisers, {'admin'})


if __name__ == '__main__':
    unittest.main()
