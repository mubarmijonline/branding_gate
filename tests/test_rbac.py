"""
Policy tests for rbac.py. Pure: no database, no Flask.

The value here is not that resolve() returns a string. It is that the business
decisions behind the permission matrix are written down as assertions, so a
later edit that quietly widens someone's access fails the build instead of
shipping.
"""

import unittest

import negotiation_workflow
import rbac


class VocabularyTest(unittest.TestCase):
    def test_every_granted_permission_exists_in_the_vocabulary(self):
        for role_code, grants in rbac.SEED_MATRIX.items():
            for code in grants:
                with self.subTest(role=role_code, permission=code):
                    self.assertIn(code, rbac.PERMISSIONS)

    def test_every_grant_uses_a_valid_scope(self):
        for role_code, grants in rbac.SEED_MATRIX.items():
            for code, scope in grants.items():
                with self.subTest(role=role_code, permission=code):
                    self.assertIn(scope, rbac.SCOPES)

    def test_every_role_in_the_matrix_is_a_declared_role(self):
        self.assertEqual(set(rbac.SEED_MATRIX), set(rbac.ROLES))

    def test_every_role_names_a_declared_department_and_level(self):
        for code, (name, dept, level) in rbac.ROLES.items():
            with self.subTest(role=code):
                self.assertTrue(name)
                self.assertIn(dept, rbac.DEPARTMENTS)
                self.assertIn(level, (0, 1, 2, 3))

    def test_scopeless_permissions_are_real_permissions(self):
        for code in rbac.SCOPELESS_PERMISSIONS:
            with self.subTest(permission=code):
                self.assertIn(code, rbac.PERMISSIONS)

    def test_seed_rows_covers_every_grant(self):
        expected = sum(len(g) for g in rbac.SEED_MATRIX.values())
        self.assertEqual(len(rbac.seed_rows()), expected)


class ResolveTest(unittest.TestCase):
    def test_absent_permission_is_denied(self):
        self.assertIsNone(rbac.resolve({}, 'sales_request.view'))
        self.assertIsNone(rbac.resolve(None, 'sales_request.view'))

    def test_held_permission_returns_its_scope(self):
        self.assertEqual(rbac.resolve({'sales_request.view': 'team'}, 'sales_request.view'), 'team')

    def test_a_junk_scope_is_treated_as_denied(self):
        self.assertIsNone(rbac.resolve({'sales_request.view': 'everything'}, 'sales_request.view'))

    def test_unknown_permission_code_raises(self):
        with self.assertRaises(rbac.UnknownPermission):
            rbac.resolve({}, 'sales_request.teleport')

    def test_widest_picks_the_broadest_scope(self):
        self.assertEqual(rbac.widest('own', 'department', 'team'), 'department')
        self.assertEqual(rbac.widest(None, 'own'), 'own')
        self.assertIsNone(rbac.widest(None, 'nonsense'))


class AllowedUserIdsTest(unittest.TestCase):
    REPORTS = [8, 9]
    DEPARTMENT = [7, 8, 9, 10]

    def ids(self, scope):
        return rbac.allowed_user_ids(scope, 7, self.REPORTS, self.DEPARTMENT)

    def test_all_is_unrestricted(self):
        self.assertIsNone(self.ids('all'))

    def test_own_is_just_the_caller(self):
        self.assertEqual(self.ids('own'), [7])

    def test_team_is_the_caller_plus_direct_reports(self):
        self.assertEqual(self.ids('team'), [7, 8, 9])

    def test_department_is_the_caller_plus_the_department(self):
        self.assertEqual(self.ids('department'), [7, 8, 9, 10])

    def test_team_scope_always_includes_the_caller_even_with_no_reports(self):
        self.assertEqual(rbac.allowed_user_ids('team', 7, [], []), [7])

    def test_an_unknown_scope_grants_nothing_rather_than_everything(self):
        self.assertEqual(self.ids('galaxy'), [])
        self.assertEqual(rbac.allowed_user_ids(None, 7), [])


class PolicyDecisionTest(unittest.TestCase):
    """The agreed business rules, written down so they cannot drift silently."""

    def holders(self, code):
        return {role for role, grants in rbac.SEED_MATRIX.items() if code in grants}

    def test_selling_price_belongs_to_pricing_alone(self):
        self.assertEqual(
            self.holders('sales_item.price'),
            {'admin', 'pricing_manager', 'pricing_specialist'},
        )

    def test_no_sales_or_account_role_can_set_a_selling_price(self):
        for role in rbac.SEED_MATRIX:
            if role.startswith(('sales_', 'account_')):
                with self.subTest(role=role):
                    self.assertNotIn('sales_item.price', rbac.SEED_MATRIX[role])

    def test_a_pricing_specialist_prepares_but_does_not_decide(self):
        self.assertIn('sales_item.price', rbac.SEED_MATRIX['pricing_specialist'])
        self.assertNotIn('negotiation.decide_pricing', rbac.SEED_MATRIX['pricing_specialist'])
        self.assertIn('negotiation.decide_pricing', rbac.SEED_MATRIX['pricing_manager'])

    def test_cost_entry_belongs_to_operations(self):
        self.assertEqual(
            self.holders('sales_item.cost'),
            {'admin', 'operations_manager', 'operations_team_leader', 'operations_member'},
        )

    def test_company_financials_are_finance_and_ceo_only(self):
        self.assertEqual(
            self.holders('finance_report.view'),
            {'admin', 'finance_manager', 'finance_member'},
        )

    def test_every_head_manager_and_team_leader_approves_expenses(self):
        for role, (_name, _dept, level) in rbac.ROLES.items():
            if role in ('admin', 'assistant'):
                continue
            grants = rbac.SEED_MATRIX[role]
            with self.subTest(role=role, level=level):
                if level in (rbac.LEVEL_HEAD, rbac.LEVEL_TEAM_LEADER):
                    self.assertIn('expense_tracking.approve_manager', grants)
                else:
                    self.assertNotIn('expense_tracking.approve_manager', grants)

    def test_manager_expense_approval_scope_matches_the_level(self):
        expected = {rbac.LEVEL_HEAD: 'department', rbac.LEVEL_TEAM_LEADER: 'team'}
        for role, (_n, _d, level) in rbac.ROLES.items():
            grants = rbac.SEED_MATRIX[role]
            if role == 'admin' or 'expense_tracking.approve_manager' not in grants:
                continue
            with self.subTest(role=role):
                self.assertEqual(grants['expense_tracking.approve_manager'], expected[level])

    def test_the_assistant_is_not_a_shadow_admin(self):
        grants = rbac.SEED_MATRIX['assistant']
        for code, scope in grants.items():
            with self.subTest(permission=code):
                # Managing one's own expense claim is not company-wide power.
                if code.startswith('expense.'):
                    self.assertEqual(scope, 'own')
                    continue
                self.assertFalse(code.endswith('.delete'))
                self.assertNotIn('approve', code)
                self.assertFalse(code.startswith('finance_txn.'))
                self.assertFalse(code.startswith('user_balance.'))
        self.assertNotIn('user.create', grants)
        self.assertNotIn('user.edit', grants)
        self.assertNotIn('role.assign', grants)

    def test_only_admin_administers_users_roles_and_departments(self):
        for code in ('user.create', 'user.edit', 'user.delete', 'role.assign', 'department.edit'):
            with self.subTest(permission=code):
                self.assertEqual(self.holders(code), {'admin'})

    def test_a_member_sees_only_their_own_sales_requests(self):
        for role in ('sales_member', 'account_member'):
            with self.subTest(role=role):
                self.assertEqual(rbac.SEED_MATRIX[role]['sales_request.view'], 'own')

    def test_leaders_and_heads_widen_by_exactly_one_step(self):
        self.assertEqual(rbac.SEED_MATRIX['sales_team_leader']['sales_request.view'], 'team')
        self.assertEqual(rbac.SEED_MATRIX['sales_head']['sales_request.view'], 'department')

    def test_only_the_sales_head_decides_a_negotiation_for_sales(self):
        self.assertEqual(
            self.holders('negotiation.decide_sales_head'),
            {'admin', 'sales_head'},
        )

    def test_personal_expenses_are_always_own_scope(self):
        for role, grants in rbac.SEED_MATRIX.items():
            if role == 'admin':
                continue
            for code, scope in grants.items():
                if code.startswith('expense.'):
                    with self.subTest(role=role, permission=code):
                        self.assertEqual(scope, 'own')

    def test_admin_holds_every_permission_at_full_scope(self):
        self.assertEqual(set(rbac.SEED_MATRIX['admin']), set(rbac.PERMISSIONS))
        self.assertEqual(set(rbac.SEED_MATRIX['admin'].values()), {'all'})


class NegotiationActorTest(unittest.TestCase):
    """The negotiation workflow must stay reachable after the role rename."""

    def test_role_codes_map_onto_workflow_actors(self):
        self.assertEqual(rbac.negotiation_actor('sales_head'), 'sales_head')
        self.assertEqual(rbac.negotiation_actor('pricing_manager'), 'pricing')
        self.assertEqual(rbac.negotiation_actor('pricing_specialist'), 'pricing')
        self.assertEqual(rbac.negotiation_actor('operations_member'), 'operation')
        self.assertEqual(rbac.negotiation_actor('admin'), 'sales_head')

    def test_a_role_with_no_workflow_part_maps_to_nothing(self):
        self.assertIsNone(rbac.negotiation_actor('marketing_member'))
        self.assertIsNone(rbac.negotiation_actor('not_a_role'))

    def test_every_workflow_actor_is_reachable_from_some_role(self):
        actors_in_workflow = {key[1] for key in negotiation_workflow._TRANSITIONS}
        reachable = {rbac.negotiation_actor(role) for role in rbac.ROLES}
        for actor in actors_in_workflow:
            with self.subTest(actor=actor):
                self.assertIn(actor, reachable)

    def test_every_mapped_role_code_is_a_declared_role(self):
        for role_code in rbac._NEGOTIATION_ACTORS:
            with self.subTest(role=role_code):
                self.assertIn(role_code, rbac.ROLES)


if __name__ == '__main__':
    unittest.main()
