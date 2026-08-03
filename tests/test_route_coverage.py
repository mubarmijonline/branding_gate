"""
Every route is either explicitly public or carries a permission gate.

This is the test that keeps "74 ungated routes" from happening again. It
imports the app and walks the URL map; it never touches MySQL and runs in
under a second, so there is no excuse not to run it.
"""

import unittest

import branding_gate
import rbac

# Read the real list off the application rather than restating it, so the two
# can never drift apart.
PUBLIC_ENDPOINTS = branding_gate.PUBLIC_ENDPOINTS


class RouteCoverageTest(unittest.TestCase):
    def rules(self):
        return sorted(branding_gate.app.url_map.iter_rules(), key=lambda r: r.rule)

    def test_every_route_is_gated_or_explicitly_public(self):
        for rule in self.rules():
            if rule.endpoint in PUBLIC_ENDPOINTS:
                continue
            view = branding_gate.app.view_functions[rule.endpoint]
            with self.subTest(endpoint=rule.endpoint, rule=rule.rule):
                self.assertTrue(
                    getattr(view, '_perms', None),
                    '%s (%s) has no permission gate' % (rule.rule, rule.endpoint),
                )

    def test_every_gate_names_a_real_permission(self):
        for rule in self.rules():
            view = branding_gate.app.view_functions[rule.endpoint]
            for code in getattr(view, '_perms', ()) or ():
                if code.startswith('legacy:'):
                    continue
                with self.subTest(endpoint=rule.endpoint, permission=code):
                    self.assertIn(code, rbac.PERMISSIONS)

    def test_the_public_list_does_not_name_routes_that_no_longer_exist(self):
        endpoints = {rule.endpoint for rule in self.rules()}
        for name in PUBLIC_ENDPOINTS:
            with self.subTest(endpoint=name):
                self.assertIn(name, endpoints)

    def test_no_route_still_uses_the_legacy_role_decorator(self):
        stragglers = [
            rule.rule for rule in self.rules()
            if any(c.startswith('legacy:')
                   for c in getattr(branding_gate.app.view_functions[rule.endpoint], '_perms', ()) or ())
        ]
        self.assertEqual(stragglers, [])

    def test_price_entry_is_gated_on_the_pricing_permission(self):
        """Decision 1, asserted against the wiring rather than the matrix."""
        for rule in self.rules():
            if rule.rule.endswith('/set-prices') or rule.rule == '/pricing':
                view = branding_gate.app.view_functions[rule.endpoint]
                with self.subTest(rule=rule.rule):
                    self.assertEqual(tuple(view._perms), ('sales_item.price',))

    def test_user_administration_is_admin_only_in_practice(self):
        admin_only = {'user.create', 'user.edit', 'user.delete', 'department.edit'}
        for rule in self.rules():
            view = branding_gate.app.view_functions[rule.endpoint]
            codes = set(getattr(view, '_perms', ()) or ())
            if codes & admin_only:
                holders = {role for role, grants in rbac.SEED_MATRIX.items()
                           if codes & set(grants)}
                with self.subTest(rule=rule.rule):
                    self.assertEqual(holders, {'admin'})


if __name__ == '__main__':
    unittest.main()
