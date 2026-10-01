"""
Targets for every team, down the reporting line.

Targets were a Sales feature: only the Sales Head, Sales team leaders and
Sales members held target.view / target.assign. Asked for: each team's head
sets their team leaders' targets, a team leader sees theirs and sets their own
people's, everyone sees their own -- reached from each team's page and, for
Pricing, from its own menu. Gamal Gaber, Account Director with pricing,
held no target permission at all, so there was no target anywhere for him.

The screen itself was never Sales-only: what you see follows your scope and
what you set follows the reporting line. Only the grants and the way in were.
"""

import os
import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate
import rbac

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class GrantsByLevelTest(unittest.TestCase):

    def test_every_department_follows_the_reporting_line(self):
        for role_code, (_name, dept, level) in rbac.ROLES.items():
            grants = rbac.SEED_MATRIX.get(role_code, {})
            with self.subTest(role=role_code):
                if level == rbac.LEVEL_HEAD:
                    self.assertEqual(grants.get('target.assign'), 'department')
                    self.assertEqual(grants.get('target.view'), 'department')
                elif level == rbac.LEVEL_TEAM_LEADER:
                    self.assertEqual(grants.get('target.assign'), 'team')
                    self.assertEqual(grants.get('target.view'), 'team')
                elif level == rbac.LEVEL_MEMBER:
                    self.assertEqual(grants.get('target.view'), 'own')
                    self.assertNotIn('target.assign', grants)

    def test_sales_did_not_narrow(self):
        self.assertEqual(rbac.SEED_MATRIX['sales_head']['target.assign'], 'department')
        self.assertEqual(rbac.SEED_MATRIX['sales_team_leader']['target.assign'], 'team')


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def close(self): pass


class GamalTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self._cursor())
        branding_gate.app.config['TESTING'] = True
        cur = self._cursor()
        # The grants as rbac.py defines them, inside this transaction.
        cur.execute("SELECT id FROM rbac_role WHERE code = 'account_director'")
        role_id = cur.fetchone()['id']
        for code in ('target.view', 'target.assign'):
            cur.execute("INSERT IGNORE INTO permission (code, description) VALUES (%s, %s)",
                        (code, rbac.PERMISSIONS[code]))
            cur.execute("""INSERT INTO role_permission (role_id, permission_code, scope)
                           VALUES (%s, %s, 'department')
                           ON DUPLICATE KEY UPDATE scope = 'department'""", (role_id, code))
        cur.close()

    def _undo(self):
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _client(self, user_id=400):
        perms, role = branding_gate.load_permissions(user_id)
        client = branding_gate.app.test_client()
        with client.session_transaction() as s:
            s.update({'user_id': user_id, 'mobile': 'm', 'email': 'e', 'username': 'u',
                      'name': 'Gamal', 'roles': [role], 'perms': perms, 'role_code': role})
        return client, perms

    def test_gamal_sets_targets_for_his_account_team(self):
        client, perms = self._client()
        self.assertEqual(perms.get('target.assign'), 'department')
        rows = client.get('/api/targets').get_json().get('rows') or []
        names = {r.get('name') for r in rows}
        self.assertIn('Sarah Gaber', names)

    def test_gamal_finds_targets_in_the_pricing_menu(self):
        client, _ = self._client()
        html = client.get('/home').get_data(as_text=True)
        start = html.find('id="pricingDropdown"')
        self.assertNotEqual(start, -1, 'Pricing is not a menu for Gamal')
        menu = html[start:html.find('</li>', start)]
        self.assertIn('href="/targets"', menu)
        self.assertIn('href="/pricing"', menu)


class WayInTest(unittest.TestCase):

    def test_every_team_page_offers_targets(self):
        for team, actions in branding_gate.TEAM_ACTIONS.items():
            with self.subTest(team=team):
                self.assertEqual([a[3] for a in actions].count('targets_page'), 1)

    def test_the_page_is_not_called_sales_targets(self):
        with open(os.path.join(ROOT, 'templates', 'targets.html'), encoding='utf-8') as handle:
            page = handle.read()
        self.assertIn('<h1>Targets</h1>', page)
        self.assertNotIn('<h1>Sales targets</h1>', page)


if __name__ == '__main__':
    unittest.main()
