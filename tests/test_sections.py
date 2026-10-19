"""
The navbar menus and the home cards are one list.

They used to be gated separately and drifted: a 2D designer was offered Sales
and Operations cards for menus the navbar hid, an Assistant an Admin card, a
Sales Head an Admin menu they only earned by holding client.edit.
"""

import os
import re
import unittest

import rbac


TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')


def _read(name):
    with open(os.path.join(TEMPLATES, name), encoding='utf-8') as handle:
        return handle.read()


# What each role is meant to see. One line per role: change this and the two
# pages follow, or the test says which one did not.
EXPECTED = {
    'admin':                  ['admin', 'sales', 'operations', 'pricing', 'finance',
                               'marketing', 'account', 'design_2d', 'design_3d'],
    'assistant':              ['sales'],
    'sales_head':             ['sales'],
    'sales_team_leader':      ['sales'],
    'sales_member':           ['sales'],
    'marketing_manager':      ['marketing'],
    'marketing_member':       ['marketing'],
    'finance_manager':        ['finance'],
    'finance_member':         ['finance'],
    'account_director':       ['sales', 'account'],
    'account_team_leader':    ['sales', 'account'],
    'account_member':         ['sales', 'account'],
    'design_2d_head':         ['design_2d'],
    'design_2d_member':       ['design_2d'],
    'design_3d_head':         ['design_3d'],
    # Purchasing brings supplier.edit, and Supplier lives on the Admin menu --
    # the same reason the Operations Manager sees it.
    'design_3d_purchasing':   ['admin', 'design_3d'],
    'design_3d_member':       ['design_3d'],
    'operations_manager':     ['admin', 'operations'],
    'operations_team_leader': ['operations'],
    'operations_member':      ['operations'],
    'pricing_manager':        ['pricing'],
    'pricing_specialist':     ['pricing'],
}


class SectionPolicyTest(unittest.TestCase):

    def test_every_role_sees_what_it_is_meant_to(self):
        for role_code in rbac.ROLES:
            self.assertEqual(
                sorted(rbac.sections(rbac.SEED_MATRIX[role_code])),
                sorted(EXPECTED[role_code]),
                role_code,
            )

    def test_no_role_is_left_without_a_section(self):
        # A landing page with no cards is indistinguishable from a broken one.
        for role_code in rbac.ROLES:
            self.assertTrue(rbac.sections(rbac.SEED_MATRIX[role_code]), role_code)

    def test_nothing_is_granted_by_an_empty_permission_set(self):
        self.assertEqual(rbac.sections({}), [])
        self.assertEqual(rbac.sections(None), [])

    def test_reading_a_sales_request_is_not_the_sales_section(self):
        # Operations, Pricing, Finance and both design ladders all read sales
        # requests as part of their own work.
        for role_code in ('operations_member', 'pricing_specialist',
                          'finance_member', 'design_2d_member'):
            self.assertIn('sales_request.view', rbac.SEED_MATRIX[role_code], role_code)
            self.assertNotIn('sales', rbac.sections(rbac.SEED_MATRIX[role_code]), role_code)

    def test_editing_a_client_is_not_the_admin_section(self):
        # Client is reachable from the Sales menu, so client.edit alone must not
        # hand the Sales ladder an Admin menu.
        for role_code in ('sales_head', 'sales_team_leader', 'account_director'):
            self.assertIn('client.edit', rbac.SEED_MATRIX[role_code], role_code)
            self.assertNotIn('admin', rbac.sections(rbac.SEED_MATRIX[role_code]), role_code)


class SectionSurfaceTest(unittest.TestCase):
    """Both pages spell the same keys."""

    def test_the_home_page_has_a_card_for_every_section(self):
        home = _read('home.html')
        cards = set(re.findall(r"^  '([a-z0-9_]+)': \{$", home, re.M))
        self.assertEqual(cards, set(EXPECTED['admin']))

    def test_the_navbar_gates_its_menus_on_the_shared_list(self):
        navbar = _read('main.html')
        for key in ('admin', 'sales', 'operations', 'pricing', 'finance'):
            self.assertIn("'%s' in nav_sections" % key, navbar, key)

    def test_the_navbar_offers_every_portal(self):
        # These are built server-side rather than gated one by one, because four
        # of them side by side wrapped the navbar onto a second line.
        import branding_gate
        keys = [key for key, _label, _icon, _endpoint in branding_gate.NAV_PORTALS]
        self.assertEqual(keys, ['marketing', 'account', 'design_2d', 'design_3d'])
        self.assertIn('nav_portals', _read('main.html'))

    def test_the_home_page_reads_sections_not_permissions(self):
        home = _read('home.html')
        self.assertIn('window.USER_SECTIONS', home)
        self.assertNotIn('PORTAL_PERMISSION', home)


if __name__ == '__main__':
    unittest.main()
