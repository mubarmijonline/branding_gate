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
                     'sales_member', 'account_director', 'account_team_leader', 'admin'):
            cur.execute("SELECT id FROM rbac_role WHERE code = %s", (code,))
            self.roles[code] = cur.fetchone()['id']

        self.ops_head = self._user('pr-ops-head', 'operations_manager', 'operations')
        self.ops_member = self._user('pr-ops-member', 'operations_member', 'operations')
        self.sales_head = self._user('pr-sales-head', 'sales_head', 'sales')
        self.sales_member = self._user('pr-sales-member', 'sales_member', 'sales')
        self.account_head = self._user('pr-account-head', 'account_director', 'account')
        self.account_leader = self._user('pr-account-leader', 'account_team_leader', 'account')
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
            'email_address': 'a@b.example', 'primary_phone': '01000000000'})

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

    def test_client_request_phone_fields_are_normalized_before_saving(self):
        response = self._client_for(self.sales_member).post('/api/party-requests', json={
            'kind': 'client',
            'client_name': 'Spaced Phone',
            'mobile_number': '0 1226401477',
            'secondary_mobile_number': ' 0 100 200 3000 ',
            'email_address': 'spaced-phone@example.com',
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = json.loads(self._latest()['payload'])
        self.assertEqual(payload['mobile_number'], '01226401477')
        self.assertEqual(payload['secondary_mobile_number'], '01002003000')

    def test_account_team_leader_may_request_a_company_and_head_adds_it(self):
        response = self._client_for(self.account_leader).post('/api/party-requests', json={
            'kind': 'company',
            'company_name': 'Requested Parent Company',
            'industry_sector': 'Healthcare',
            'address': 'Cairo',
            'phone_number': '+20 100 555 7777',
            'email_address': ' RequestedCompany@Example.COM ',
            'primary_contact_person': 'Tadrous Raouf',
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        request_id = self._latest()['id']

        response = self._client_for(self.account_head).post(
            '/api/party-requests/%d/head-approve' % request_id, json={})

        self.assertEqual(response.status_code, 200, response.get_json())
        cur = self._cursor()
        cur.execute("SELECT phone_number, email_address FROM company WHERE company_name = %s",
                    ('Requested Parent Company',))
        row = cur.fetchone()
        cur.close()
        self.assertEqual(row['phone_number'], '01005557777')
        self.assertEqual(row['email_address'], 'requestedcompany@example.com')

    def test_party_request_rejects_invalid_contact_fields_as_bad_input(self):
        response = self._client_for(self.sales_member).post('/api/party-requests', json={
            'kind': 'client',
            'client_name': 'Bad Phone',
            'mobile_number': '01312345678',
            'email_address': 'client@example.com',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('Egyptian mobile', response.get_json()['error'])

    def test_existing_request_phone_fields_are_normalized_when_read(self):
        cur = self._cursor()
        cur.execute("""
            INSERT INTO party_request (request_code, kind, payload, status, requested_by)
            VALUES ('CLR-SPACE', 'client',
                    '{"client_name":"Old","mobile_number":"0 1226401477","email_address":"old@example.com"}',
                    'pending_head', %s)
        """, (self.sales_member,))
        cur.close()

        response = self._client_for(self.sales_head).get('/api/party-requests?kind=client')
        self.assertEqual(response.status_code, 200, response.get_json())
        rows = response.get_json()['requests']
        request = next(row for row in rows if row['request_code'] == 'CLR-SPACE')
        self.assertEqual(request['payload']['mobile_number'], '01226401477')

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
            'primary_phone': '01100000000', 'address': 'Somewhere', 'website': 'example.com'})
        head = self._client_for(self.ops_head).get('/api/party-requests').get_json()
        payload = head['requests'][0]['payload']
        self.assertEqual(payload['supplier_name'], 'Full Detail')
        self.assertEqual(payload['address'], 'Somewhere')
        self.assertEqual(payload['website'], 'example.com')


class PartyRequestNotificationTest(PartyRequestFlowTest):
    """
    Every step of a supplier request reaches the person waiting on it.

    The calls existed but carried no destination, so the tray had to guess the
    page from the words. And the Approvals menu offered client and company
    requests but not supplier ones, which is where the Operations Head decides
    them.
    """

    def setUp(self):
        super().setUp()
        self.sent = []
        self._real_notify = branding_gate.notify_users

        def capture(user_ids, title, content, link=None):
            self.sent.append({'to': sorted(int(u) for u in (user_ids or []) if u),
                              'title': title, 'content': content, 'link': link})
            return len(user_ids or [])

        branding_gate.notify_users = capture
        branding_gate.notify_user = (
            lambda user_id, title, content, link=None:
            capture([user_id], title, content, link=link))

    def tearDown(self):
        branding_gate.notify_users = self._real_notify
        branding_gate.notify_user = (
            lambda user_id, title, content, link=None:
            self._real_notify([user_id], title, content, link=link))
        super().tearDown()

    def _for(self, user_id):
        return [n for n in self.sent if user_id in n['to']]

    def test_the_head_is_told_a_supplier_has_been_asked_for(self):
        self.sent = []
        self._ask_supplier(self.ops_member)
        told = self._for(self.ops_head)
        self.assertTrue(told, 'the head was not told: %s' % self.sent)
        self.assertIn('supplier request', told[0]['title'].lower())
        self.assertEqual(told[0]['link'], '/supplier')

    def test_the_requester_is_told_it_was_approved(self):
        self._ask_supplier(self.ops_member)
        request_id = self._latest()['id']
        self.sent = []
        response = self._client_for(self.ops_head).post(
            '/api/party-requests/%d/head-approve' % request_id, json={})
        self.assertEqual(response.status_code, 200, response.get_json())
        told = self._for(self.ops_member)
        self.assertTrue(told, 'the requester was not told: %s' % self.sent)
        self.assertIn('added', told[0]['title'].lower())
        self.assertEqual(told[0]['link'], '/supplier')

    def test_the_requester_is_told_it_was_declined_and_why(self):
        self._ask_supplier(self.ops_member)
        request_id = self._latest()['id']
        self.sent = []
        self._client_for(self.ops_head).post(
            '/api/party-requests/%d/reject' % request_id,
            json={'reason': 'We already buy this from someone else'})
        told = self._for(self.ops_member)
        self.assertTrue(told, 'the requester was not told: %s' % self.sent)
        self.assertIn('declined', told[0]['title'].lower())
        self.assertIn('already buy this', told[0]['content'])
        self.assertEqual(told[0]['link'], '/supplier')

    def test_the_approvals_menu_offers_supplier_requests(self):
        source = open('templates/main.html', encoding='utf-8').read()
        self.assertIn("{% set can_open_suppliers", source)
        self.assertIn('Supplier Requests', source)
        # Beside the other two, in the same menu.
        approvals = source[source.index('id="approvalsDropdown"'):]
        approvals = approvals[:approvals.index('</li>')]
        for entry in ('Client Requests', 'Company Requests', 'Supplier Requests'):
            self.assertIn(entry, approvals, entry)


class SupplierDirectAddTest(PartyRequestFlowTest):
    """
    Whoever may add a supplier outright is not asked to request one.

    The Operations Head holds both `supplier.create` and, by being in
    Operations, `supplier_request.create` -- so the page offered him a request
    that he would then approve himself. The card stays, because deciding other
    people's requests is the other half of it; the button to raise one does
    not.
    """

    def _page(self, actor):
        return self._client_for(actor).get('/supplier').get_data(as_text=True)

    def test_the_head_gets_the_add_button_and_no_request_button(self):
        html = self._page(self.ops_head)
        self.assertIn('data-target="#addSupplierModal"', html)
        self.assertNotIn('id="partyRequestNew"', html)
        # ...but still the card, to decide what his team asks for.
        self.assertIn('id="partyRequestCard"', html)

    def test_a_member_gets_the_request_button_and_no_add_button(self):
        html = self._page(self.ops_member)
        self.assertNotIn('data-target="#addSupplierModal"', html)
        self.assertIn('id="partyRequestNew"', html)


class SupplierEmailOptionalTest(PartyRequestFlowTest):
    """
    A supplier reached only by phone.

    The email was required in four places at once -- the request rules, the
    request form, both supplier forms and a NOT NULL column -- so the address
    being typed in was often a placeholder. Two suppliers on the live system
    share one.
    """

    def test_a_supplier_can_be_asked_for_without_an_email(self):
        response = self._client_for(self.ops_member).post('/api/party-requests', json={
            'kind': 'supplier', 'supplier_name': 'Phone Only Supplier',
            'primary_phone': '01000000000'})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self._latest()['status'], 'pending_head')

    def test_the_name_is_still_required(self):
        response = self._client_for(self.ops_member).post('/api/party-requests', json={
            'kind': 'supplier', 'primary_phone': '01000000000'})
        self.assertEqual(response.status_code, 400)

    def test_a_client_still_needs_one(self):
        # Only the supplier rule changed.
        self.assertIn('email_address', branding_gate.PARTY_REQUIRED['client'])
        self.assertNotIn('email_address', branding_gate.PARTY_REQUIRED['supplier'])

    def test_adding_one_directly_without_an_email_works(self):
        response = self._client_for(self.ops_head).post('/api/suppliers/add', json={
            'supplier_name': 'Phone Only Direct', 'supplier_type': 'Materials',
            'status': 'active', 'date_added': '2026-09-07',
            'contact_person_name': 'Mahmoud', 'primary_phone': '01000000321',
            'preferred_contact_method': 'phone'})
        self.assertEqual(response.status_code, 200, response.get_json())
        cur = self._cursor()
        cur.execute("SELECT email_address FROM supplier WHERE primary_phone = '01000000321'")
        self.assertIsNone(cur.fetchone()['email_address'])
        cur.close()

    def test_two_suppliers_with_no_email_are_not_duplicates(self):
        for phone in ('01000000322', '01000000323'):
            response = self._client_for(self.ops_head).post('/api/suppliers/add', json={
                'supplier_name': 'No Email ' + phone, 'supplier_type': 'Materials',
                'status': 'active', 'date_added': '2026-09-07',
                'contact_person_name': 'Mahmoud', 'primary_phone': phone,
                'preferred_contact_method': 'phone'})
            self.assertEqual(response.status_code, 200, response.get_json())

    def test_an_email_that_is_given_is_still_checked(self):
        payload = {'supplier_name': 'With Email', 'supplier_type': 'Materials',
                   'status': 'active', 'date_added': '2026-09-07',
                   'contact_person_name': 'Mahmoud', 'primary_phone': '01000000324',
                   'preferred_contact_method': 'phone',
                   'email_address': 'not-an-email'}
        response = self._client_for(self.ops_head).post('/api/suppliers/add', json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn('valid email', response.get_json()['error'])


class SupplierTypeTest(PartyRequestFlowTest):
    """
    A supplier type typed under "Other" is that type.

    Choosing "Other" and typing "Production" stored the word **Other**, with
    "Production" in a second column no list or filter reads -- so those
    suppliers all showed as "Other". Two on the live system did.
    """

    def _add(self, name, phone, supplier_type, other=''):
        return self._client_for(self.ops_head).post('/api/suppliers/add', json={
            'supplier_name': name, 'supplier_type': supplier_type,
            'other_supplier_type': other, 'status': 'active',
            'date_added': '2026-09-08', 'contact_person_name': 'Tester',
            'primary_phone': phone, 'preferred_contact_method': 'phone'})

    def _type_of(self, phone):
        cur = self._cursor()
        cur.execute("SELECT supplier_type FROM supplier WHERE primary_phone = %s", (phone,))
        row = cur.fetchone()
        cur.close()
        return row['supplier_type'] if row else None

    def test_the_typed_word_becomes_the_type(self):
        response = self._add('Typed Type', '01000000401', 'Other', 'Fabrication')
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self._type_of('01000000401'), 'Fabrication')

    def test_a_chosen_type_is_left_alone(self):
        self._add('Chosen Type', '01000000402', 'Equipment')
        self.assertEqual(self._type_of('01000000402'), 'Equipment')

    def test_other_with_nothing_typed_stays_other(self):
        # Nothing better to record: the form requires the text, but the route
        # must not invent one.
        self._add('Empty Other', '01000000403', 'Other', '   ')
        self.assertEqual(self._type_of('01000000403'), 'Other')

    def test_a_typed_type_is_offered_next_time(self):
        self._add('Typed Type', '01000000404', 'Other', 'Fabrication')
        response = self._client_for(self.ops_head).get('/api/suppliers/types')
        self.assertEqual(response.status_code, 200, response.get_json())
        types = response.get_json()['types']
        self.assertIn('Fabrication', types)
        # The built-in ones are still there, and "Other" is not one of them:
        # it is the control that reveals the text box, not a type.
        self.assertIn('Equipment', types)
        self.assertNotIn('Other', types)

    def test_the_list_is_sorted_and_free_of_duplicates(self):
        self._add('One', '01000000405', 'Other', 'Fabrication')
        self._add('Two', '01000000406', 'Other', 'Fabrication')
        types = self._client_for(self.ops_head).get(
            '/api/suppliers/types').get_json()['types']
        self.assertEqual(len(types), len(set(types)))
        self.assertEqual(types, sorted(types, key=str.lower))

    def test_the_resolver_itself(self):
        resolve = branding_gate.resolve_supplier_type
        self.assertEqual(resolve({'supplier_type': 'Other',
                                  'other_supplier_type': 'Production'}),
                         ('Production', 'Production'))
        self.assertEqual(resolve({'supplier_type': 'Equipment'}), ('Equipment', ''))
        # Case does not matter for the control word.
        self.assertEqual(resolve({'supplier_type': 'other',
                                  'other_supplier_type': ' Signage '})[0], 'Signage')


class EntityPermissionTest(unittest.TestCase):
    """
    The Operations Head adds entities.

    The page offered an "Add Entity" button to anyone who could view the page,
    and the route behind it wanted `entity.create`, which only admin held. So
    the Head pressed the button and was told Forbidden.
    """

    def test_the_operations_head_may_create_and_edit_an_entity(self):
        head = rbac.SEED_MATRIX['operations_manager']
        self.assertEqual(head.get('entity.create'), 'all')
        self.assertEqual(head.get('entity.edit'), 'all')

    def test_the_head_may_delete_one_but_the_route_still_guards_it(self):
        # The grant is theirs; the safety is in the route, which refuses any
        # entity that still holds inventory whoever is asking.
        self.assertEqual(rbac.SEED_MATRIX['operations_manager'].get('entity.delete'), 'all')
        holders = sorted(code for code, grants in rbac.SEED_MATRIX.items()
                         if 'entity.delete' in grants)
        self.assertEqual(holders, ['admin', 'operations_manager'])
        source = open('branding_gate.py', encoding='utf-8').read()
        self.assertIn('Cannot delete entity with {count} inventory items', source)

    def test_a_team_leader_still_cannot_touch_entities(self):
        leader = rbac.SEED_MATRIX['operations_team_leader']
        self.assertEqual(leader.get('entity.view'), 'all')
        for code in ('entity.create', 'entity.edit', 'entity.delete'):
            self.assertNotIn(code, leader, code)

    def test_the_page_offers_each_button_only_where_the_route_agrees(self):
        source = open('templates/entity_management.html', encoding='utf-8').read()
        self.assertIn("{% if 'entity.create' in _p %}", source)
        self.assertIn("var CAN_EDIT_ENTITY   = {{ 'true' if 'entity.edit' in _p", source)
        self.assertIn("var CAN_DELETE_ENTITY = {{ 'true' if 'entity.delete' in _p", source)
        self.assertIn('${CAN_EDIT_ENTITY ?', source)
        self.assertIn('${CAN_DELETE_ENTITY ?', source)


class PartyRequestPolicyTest(unittest.TestCase):

    def test_clients_are_asked_for_by_sales_and_account(self):
        holders = {r for r, g in rbac.SEED_MATRIX.items() if 'client_request.create' in g}
        self.assertTrue({'sales_member', 'sales_head', 'account_member',
                         'account_director'} <= holders)
        self.assertNotIn('operations_member', holders)

    def test_companies_are_asked_for_by_sales_and_account(self):
        holders = {r for r, g in rbac.SEED_MATRIX.items() if 'company_request.create' in g}
        self.assertTrue({'sales_member', 'sales_team_leader', 'sales_head',
                         'account_member', 'account_team_leader',
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
