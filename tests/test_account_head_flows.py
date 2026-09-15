"""
Two things the account head could not do.

1. Approve a client request. CLR-38691 held a phone number in its "preferred
   contact channel", the client table only takes Phone / Email / WhatsApp /
   Other, and MySQL refused the insert: "Data truncated for column
   'preferred_contact_channel'". The channel is now read one way everywhere --
   when a request is made, when it is approved, when a client is added or
   edited -- and a value the column cannot take never reaches it.

2. See a negotiated price. Negotiations went to holders of
   negotiation.decide_sales_head -- admin and the Sales Head -- so a client's
   counter-offer on an account request never reached the account director, and
   nothing notified anybody at all. The account director now holds it for their
   department, the Sales Head list and its approve / decline routes are scoped
   to the request's owner, and the right head is told.

Rollback-based, like the other route tests here.
"""

import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate
import fixtures
import rbac


class ContactChannelTest(unittest.TestCase):

    def test_what_the_column_can_take(self):
        read = branding_gate.contact_channel
        self.assertEqual(read('Phone'), 'Phone')
        self.assertEqual(read('whatsapp'), 'WhatsApp')
        self.assertEqual(read(' EMAIL '), 'Email')
        # CLR-38691's value.
        self.assertEqual(read('+20 12 25908839'), 'Phone')
        self.assertEqual(read('In Person'), 'Other')
        self.assertIsNone(read(''))
        self.assertIsNone(read(None))
        for value in ('Phone', 'whatsapp', '+20 12 25908839', 'In Person', 'x'):
            self.assertIn(read(value), branding_gate.CONTACT_CHANNELS)


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def close(self): pass


class _Harness(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4",
                                   use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        self._real_notify = branding_gate.notify_users
        # Registered before anything can fail. A cleanup runs even when setUp
        # raises -- tearDown does not -- and a transaction left open here keeps
        # its locks on role_permission, so the next test's setUp waited on
        # them for ever. That is how one setUp error looked like a hang.
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self._cursor())
        branding_gate.app.config['TESTING'] = True
        self.sent = []
        branding_gate.notify_users = lambda ids, title, body, link=None: (
            self.sent.append({'to': sorted(int(i) for i in (ids or [])), 'title': title,
                              'link': link}) or len(ids or []))

        cur = self._cursor()
        self.departments = {}
        for code in ('account', 'sales'):
            cur.execute("SELECT id FROM department WHERE code = %s", (code,))
            self.departments[code] = cur.fetchone()['id']
        self.roles = {}
        for code in ('account_director', 'account_team_leader', 'account_member', 'sales_head'):
            cur.execute("SELECT id FROM rbac_role WHERE code = %s", (code,))
            self.roles[code] = cur.fetchone()['id']
        # These roles' grants exactly as seed_rbac.py writes them, inside this
        # transaction: delete what the database holds and insert the matrix.
        # Adding only the new grants left an old one standing -- the account
        # director's Sales Head permission from before the pages were split --
        # and the permission check re-reads the database.
        for role_code in ('account_director', 'account_team_leader', 'account_member', 'sales_head'):
            grants = rbac.SEED_MATRIX[role_code]
            for permission in grants:
                cur.execute("INSERT IGNORE INTO permission (code, description) VALUES (%s, %s)",
                            (permission, rbac.PERMISSIONS[permission]))
            cur.execute("DELETE FROM role_permission WHERE role_id = %s", (self.roles[role_code],))
            for permission, scope in grants.items():
                cur.execute("INSERT INTO role_permission (role_id, permission_code, scope) "
                            "VALUES (%s, %s, %s)", (self.roles[role_code], permission, scope))
        cur.close()

        # Heads report to someone, as the real ones do: users_holding() leaves
        # out anyone with no manager, which is how it keeps the CEO out of
        # every fan-out.
        self.head = self._make_user('ah-head', 'account_director', 'account', manager=1)
        self.leader = self._make_user('ah-leader', 'account_team_leader', 'account', self.head)
        self.sales_head = self._make_user('ah-sales-head', 'sales_head', 'sales', manager=1)

    def _undo(self):
        branding_gate.notify_users = self._real_notify
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _make_user(self, username, role_code, department, manager=None):
        cur = self._cursor()
        cur.execute("""INSERT INTO user (name, mobile, email, password, username, title,
                                         department_id, rbac_role_id, manager_id, is_active, date)
                       VALUES (%s, %s, %s, 'x', %s, 'Account head test', %s, %s, %s, 1, NOW())""",
                    (username, '015%08d' % (abs(hash(username)) % 10 ** 8),
                     username + '@example.com', username, self.departments[department],
                     self.roles[role_code], manager))
        user_id = cur.lastrowid
        cur.close()
        return user_id

    def _client_for(self, user_id, name='Tester'):
        perms, role_code = branding_gate.load_permissions(user_id)
        client = branding_gate.app.test_client()
        with client.session_transaction() as flask_session:
            flask_session.update({'user_id': user_id, 'mobile': 'm', 'email': 'e',
                                  'username': 'u', 'name': name, 'roles': [role_code],
                                  'perms': perms, 'role_code': role_code})
        return client


class ClientRequestApprovalTest(_Harness):

    def test_a_request_holding_a_phone_number_as_its_channel_is_approved(self):
        # CLR-38691, as it is stored.
        payload = {'client_name': 'Channel Probe Client', 'mobile_number': '01225900001',
                   'email_address': 'channel.probe@example.com',
                   'preferred_contact_channel': '+20 12 25900001'}
        cur = self._cursor()
        cur.execute("""INSERT INTO party_request (request_code, kind, payload, status, requested_by)
                       VALUES ('CLR-PROBE1', 'client', %s, 'pending_head', %s)""",
                    (branding_gate.json.dumps(payload), self.leader))
        request_id = cur.lastrowid
        cur.close()

        response = self._client_for(self.head).post(
            '/api/party-requests/%d/head-approve' % request_id, json={})
        self.assertEqual(response.status_code, 200, response.data[:300])

        cur = self._cursor()
        cur.execute("SELECT preferred_contact_channel FROM client WHERE client_name = %s",
                    ('Channel Probe Client',))
        row = cur.fetchone()
        cur.close()
        self.assertIsNotNone(row, 'the client was not created')
        self.assertEqual(row['preferred_contact_channel'], 'Phone')

    def test_a_new_request_is_stored_with_a_channel_the_column_takes(self):
        response = self._client_for(self.leader).post('/api/party-requests', json={
            'kind': 'client', 'client_name': 'Channel Probe Two',
            'mobile_number': '01225900002', 'email_address': 'channel.two@example.com',
            'preferred_contact_channel': 'In Person'})
        self.assertEqual(response.status_code, 200, response.data[:300])
        cur = self._cursor()
        cur.execute("SELECT payload FROM party_request WHERE request_code = %s",
                    (response.get_json()['request_code'],))
        stored = branding_gate.json.loads(cur.fetchone()['payload'])
        cur.close()
        self.assertEqual(stored['preferred_contact_channel'], 'Other')


class NegotiationReachesItsHeadTest(_Harness):

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        client_id = fixtures.ensure_client(cur)
        cur.execute("""INSERT INTO sales_request (client_id, title, start_date, created_by,
                                                  items_count, owner_user_id)
                       VALUES (%s, 'Account negotiation probe', CURDATE(), 'ah-test', 1, %s)""",
                    (client_id, self.leader))
        self.request_id = cur.lastrowid
        cur.execute("""INSERT INTO sales_request_items
                           (request_id, name, qty, cost_per_item, sell_per_item,
                            total_cost, total_sell, approval_status)
                       VALUES (%s, 'Negotiated item', 10, 80, 120, 800, 1200, 'pending')""",
                    (self.request_id,))
        self.item_id = cur.lastrowid
        cur.close()

    def _negotiate(self):
        return self._client_for(self.leader, 'Sarah').post(
            '/api/client-approval/items/%d/negotiate' % self.item_id,
            json={'reason': 'Client wants 100', 'expected_price': 100})

    def _pending_ids(self, user_id, line=None):
        path = '/api/sales-head/negotiations' + ('?line=%s' % line if line else '')
        response = self._client_for(user_id).get(path)
        self.assertEqual(response.status_code, 200, response.data[:300])
        body = response.get_json()
        rows = body.get('negotiations') or body.get('data') or []
        return {row['id'] for row in rows}

    def test_the_account_head_sees_it_and_the_sales_head_does_not(self):
        created = self._negotiate()
        self.assertEqual(created.status_code, 200, created.data[:300])
        negotiation_id = created.get_json()['negotiation_id']
        self.assertIn(negotiation_id, self._pending_ids(self.head))
        self.assertNotIn(negotiation_id, self._pending_ids(self.sales_head))

    def test_the_account_head_is_told(self):
        self._negotiate()
        told = [n for n in self.sent if n['link'] == '/account-head-approval']
        self.assertTrue(told, 'nobody was notified of the negotiation')
        self.assertIn(self.head, told[0]['to'])
        self.assertNotIn(self.sales_head, told[0]['to'])

    def test_the_other_head_cannot_decide_on_it(self):
        negotiation_id = self._negotiate().get_json()['negotiation_id']
        outsider = self._client_for(self.sales_head)
        approve = outsider.post('/api/sales-head/negotiations/%d/approve' % negotiation_id,
                                json={'notes': 'x'})
        self.assertEqual(approve.status_code, 403)
        decline = outsider.post('/api/sales-head/negotiations/%d/decline' % negotiation_id,
                                json={'reason': 'x'})
        self.assertEqual(decline.status_code, 403)

    def test_the_account_head_can_decide_on_it(self):
        negotiation_id = self._negotiate().get_json()['negotiation_id']
        response = self._client_for(self.head).post(
            '/api/sales-head/negotiations/%d/approve' % negotiation_id, json={'notes': 'fine'})
        self.assertEqual(response.status_code, 200, response.data[:300])

    def test_the_account_director_holds_it_for_the_department(self):
        self.assertEqual(rbac.SEED_MATRIX['account_director'].get('negotiation.decide_account_head'),
                         'department')
        self.assertIsNone(rbac.SEED_MATRIX['account_director'].get('negotiation.decide_sales_head'))

    def test_each_head_opens_their_own_page_and_not_the_other(self):
        head, sales_head = self._client_for(self.head), self._client_for(self.sales_head)
        self.assertEqual(head.get('/account-head-approval').status_code, 200)
        self.assertEqual(head.get('/sales-head-approval').status_code, 403)
        self.assertEqual(sales_head.get('/sales-head-approval').status_code, 200)
        self.assertEqual(sales_head.get('/account-head-approval').status_code, 403)

    def test_the_account_page_lists_only_the_account_line(self):
        negotiation_id = self._negotiate().get_json()['negotiation_id']
        self.assertIn(negotiation_id, self._pending_ids(self.head, 'account'))
        self.assertNotIn(negotiation_id, self._pending_ids(self.head, 'sales'))

    def test_the_answer_names_who_reviews_it(self):
        body = self._negotiate().get_json()
        self.assertEqual(body['reviewer'], 'Account Director')



class HomeQuickLinksTest(_Harness):
    """
    The home page's portal quick links follow the permissions too.

    The Sales portal is shared with Account Management, and its quick links
    were drawn with no check at all -- so the account director was offered
    "Sales Head Approval", a page that now refuses them. The links are data in
    the page for everyone; which ones are drawn is decided in the browser, so
    this runs that code in node with the account director's permissions.
    """

    def _drawn_links(self, user_id):
        import json
        import os
        import re
        import shutil
        import subprocess
        import tempfile
        if not shutil.which('node'):
            self.skipTest('node is not installed')
        html = self._client_for(user_id).get('/home').get_data(as_text=True)
        start = html.index('window.USER_PERMS = window.USER_PERMS ||')
        portals = html[start:html.index('function renderRolePortals', start)]
        card = html[html.index('function createPortalCard(portal)'):]
        card = card[:card.index('\n}\n') + 3]
        script = ('var window = {};\n' + portals + '\n' + card + '\n'
                  'var out = {};\n'
                  'Object.keys(rolePortals).forEach(function (k) {\n'
                  '  out[k] = (createPortalCard(rolePortals[k]).match(/href="([^"]+)"/g) || []);\n'
                  '});\n'
                  'console.log(JSON.stringify(out));')
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as handle:
            handle.write(script)
            path = handle.name
        try:
            result = subprocess.run(['node', path], capture_output=True, text=True, timeout=30)
        finally:
            os.unlink(path)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_the_account_director_is_offered_their_page_not_the_sales_heads(self):
        links = self._drawn_links(self.head)
        sales = ' '.join(links['sales'])
        self.assertIn('/account-head-approval', sales)
        self.assertNotIn('/sales-head-approval', sales)
        self.assertIn('/account-head-approval', ' '.join(links['account']))

    def test_the_sales_head_is_offered_theirs(self):
        sales = ' '.join(self._drawn_links(self.sales_head)['sales'])
        self.assertIn('/sales-head-approval', sales)
        self.assertNotIn('/account-head-approval', sales)


if __name__ == '__main__':
    unittest.main()
