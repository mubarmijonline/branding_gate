"""
The department portals that are blank for now.

Read-only: these probe the seeded organisation rather than creating people, so
nothing is written and nothing needs rolling back.
"""

import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate
import rbac


PORTALS = [
    ('/marketing', 'portal.marketing', 'marketing_manager', 'marketing_member'),
    ('/account',   'portal.account',   'account_director',  'account_member'),
    ('/design-2d', 'portal.design_2d', 'design_2d_head',    'design_2d_member'),
    ('/design-3d', 'portal.design_3d', 'design_3d_head',    'design_3d_member'),
]


def _a_user_holding(role_code):
    """Any seeded account with this role, or None when nobody has it."""
    conn = MySQLdb.connect(
        host="localhost", user="ps", passwd="Aa@123456", db="branding_gate",
        port=3306, charset="utf8mb4", use_unicode=True,
        cursorclass=MySQLdb.cursors.DictCursor,
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT u.id FROM user u
        JOIN rbac_role r ON r.id = u.rbac_role_id
        WHERE r.code = %s ORDER BY u.id LIMIT 1
    """, (role_code,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row['id'] if row else None


class PortalPolicyTest(unittest.TestCase):
    """A portal belongs to its department and to nobody else."""

    def test_every_portal_permission_exists(self):
        for _path, code, _head, _member in PORTALS:
            self.assertIn(code, rbac.PERMISSIONS)
            self.assertIn(code, rbac.SCOPELESS_PERMISSIONS)

    def test_a_portal_is_held_by_its_whole_department(self):
        for _path, code, head, member in PORTALS:
            self.assertEqual(rbac.SEED_MATRIX[head].get(code), 'all', head)
            self.assertEqual(rbac.SEED_MATRIX[member].get(code), 'all', member)

    def test_sales_holds_no_other_departments_portal(self):
        for role in ('sales_head', 'sales_team_leader', 'sales_member'):
            for _path, code, _head, _member in PORTALS:
                self.assertNotIn(code, rbac.SEED_MATRIX[role], '%s / %s' % (role, code))

    def test_the_account_ladder_keeps_its_portal_at_every_level(self):
        # The home page used to gate this card on client.edit, which an Account
        # Member does not hold, so the people it was for could not see it.
        for role in ('account_director', 'account_team_leader', 'account_member'):
            self.assertIn('portal.account', rbac.SEED_MATRIX[role], role)


class PortalRouteTest(unittest.TestCase):
    """The pages open for their own department and 403 for everyone else."""

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

    def test_each_portal_opens_for_its_own_department(self):
        for path, _code, head, _member in PORTALS:
            user_id = _a_user_holding(head)
            if user_id is None:
                self.skipTest('nobody holds %s in this database' % head)
            response = self._client_for(user_id).get(path)
            self.assertEqual(response.status_code, 200, path)
            # A 200 that rendered the login page would not be the portal.
            self.assertIn(b'portal-blank-card', response.data, path)

    def test_a_portal_is_refused_to_another_department(self):
        outsider = _a_user_holding('sales_member')
        if outsider is None:
            self.skipTest('no sales member in this database')
        client = self._client_for(outsider)
        for path, _code, _head, _member in PORTALS:
            self.assertEqual(client.get(path).status_code, 403, path)

    def test_the_owner_reaches_all_of_them(self):
        client = self._client_for(1)
        for path, _code, _head, _member in PORTALS:
            self.assertEqual(client.get(path).status_code, 200, path)


if __name__ == '__main__':
    unittest.main()
