"""
What is sent to 'admin' reaches every active admin, the CEO (no manager)
included: an urgent sales request waits on them. Other fan-outs still leave
the CEO out.
"""

import unittest

import branding_gate


class AdminAudienceTest(unittest.TestCase):

    def test_admins_include_the_ceo(self):
        conn, cur = branding_gate.connection()
        try:
            cur.execute("""SELECT u.id, u.manager_id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
                           WHERE r.code = 'admin' AND u.is_active = 1""")
            admins = cur.fetchall()
            cur.execute("""SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
                           WHERE r.code = 'sales_head' AND u.is_active = 1 AND u.manager_id IS NULL""")
            root_sales_heads = [r['id'] for r in cur.fetchall()]
        finally:
            cur.close()
            conn.close()
        self.assertEqual(sorted(branding_gate.get_users_by_role('admin')), sorted(a['id'] for a in admins))
        self.assertTrue(any(a['manager_id'] is None for a in admins), 'expected a CEO among the admins')
        for uid in root_sales_heads:
            self.assertNotIn(uid, branding_gate.get_users_by_role('sales'))


if __name__ == '__main__':
    unittest.main()
