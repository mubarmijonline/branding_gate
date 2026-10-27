"""
Extra permissions given from People & Access (permission_grant), on top of
the role grants that seed_rbac.py regenerates from rbac.py.

Same rolled-back connection as test_costing.py: nothing survives.
"""

import unittest

import branding_gate
from test_costing import _CostingHarness


class PermissionGrantTest(_CostingHarness):

    def _grant(self, actor, target_type, target_id, code='sales_request.delete', scope='all'):
        return self._client_for(actor).post('/api/rbac/grants', json={
            'target_type': target_type, 'target_id': target_id,
            'permission_code': code, 'scope': scope})

    def _admin(self):
        cur = self._cursor()
        cur.execute("SELECT id FROM rbac_role WHERE code = 'admin'")
        role_id = cur.fetchone()['id']
        cur.execute("""INSERT INTO user (name, mobile, email, password, username, title,
                                         department_id, rbac_role_id, manager_id, date)
                       VALUES ('grant-admin', '01799999991', 'ga@example.com', 'x', 'grant-admin',
                               'Admin', %s, %s, %s, NOW())""", (self.department_id, role_id, self.head))
        user_id = cur.lastrowid
        cur.close()
        return user_id

    def _perms(self, user_id):
        return branding_gate.load_permissions(user_id)[0]

    def test_a_person_gets_it_and_nobody_else(self):
        admin = self._admin()
        self.assertNotIn('sales_request.delete', self._perms(self.member))
        self.assertEqual(self._grant(admin, 'user', self.member).status_code, 200)
        self.assertEqual(self._perms(self.member)['sales_request.delete'], 'all')
        self.assertNotIn('sales_request.delete', self._perms(self.member_b))

    def test_a_role_reaches_everyone_holding_it(self):
        admin = self._admin()
        self._grant(admin, 'role', self.roles['operations_member'])
        self.assertIn('sales_request.delete', self._perms(self.member))
        self.assertIn('sales_request.delete', self._perms(self.outsider))
        self.assertNotIn('sales_request.delete', self._perms(self.leader))

    def test_a_department_reaches_its_people(self):
        admin = self._admin()
        self._grant(admin, 'department', self.department_id)
        self.assertIn('sales_request.delete', self._perms(self.leader))

    def test_a_team_is_the_leader_and_their_reports(self):
        admin = self._admin()
        self._grant(admin, 'team', self.leader)
        self.assertIn('sales_request.delete', self._perms(self.leader))
        self.assertIn('sales_request.delete', self._perms(self.member))
        self.assertNotIn('sales_request.delete', self._perms(self.outsider))
        self.assertNotIn('sales_request.delete', self._perms(self.head))

    def test_the_wider_scope_wins_and_regranting_changes_scope(self):
        admin = self._admin()
        # The leader holds costing.view at team; an extra at own must not narrow it.
        self._grant(admin, 'user', self.leader, 'costing.view', 'own')
        self.assertEqual(self._perms(self.leader)['costing.view'], 'team')
        self._grant(admin, 'user', self.leader, 'costing.view', 'all')
        self.assertEqual(self._perms(self.leader)['costing.view'], 'all')
        rows = self._client_for(admin).get(
            '/api/rbac/grants?target_type=user&target_id=%d' % self.leader).get_json()['grants']
        self.assertEqual(len(rows), 1)

    def test_grantees_hear_about_the_work(self):
        admin = self._admin()
        self.assertNotIn(self.member, branding_gate.users_holding('invoice.post'))
        self._grant(admin, 'user', self.member, 'invoice.post')
        self.assertIn(self.member, branding_gate.users_holding('invoice.post'))

    def test_only_role_grant_may_give_or_take(self):
        self.assertEqual(self._grant(self.head, 'user', self.member).status_code, 403)
        admin = self._admin()
        grant_id = self._grant(admin, 'user', self.member).get_json()['grants'][0]['id']
        self.assertEqual(self._client_for(self.head).delete(
            '/api/rbac/grants/%d' % grant_id).status_code, 403)
        self.assertEqual(self._client_for(admin).delete(
            '/api/rbac/grants/%d' % grant_id).status_code, 200)
        self.assertNotIn('sales_request.delete', self._perms(self.member))

    def test_nonsense_is_refused(self):
        admin = self._admin()
        self.assertEqual(self._grant(admin, 'planet', self.member).status_code, 400)
        self.assertEqual(self._grant(admin, 'user', self.member, 'no.such').status_code, 400)
        self.assertEqual(self._grant(admin, 'user', 999999999).status_code, 404)


if __name__ == '__main__':
    unittest.main()
