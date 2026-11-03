"""
My Money Requests sits on the Operations home, shown only to those whose
request goes straight to Finance (a head under the CEO, the admin), and no
longer on the main home page (Ahmed, 2026-11-03). Rollback-based.
"""

import testdb  # noqa: F401  first: the test database, not the live one
import unittest

import branding_gate
from test_supplier_accounts import SupplierAccountsTest


class MoneyRequestsSectionTest(SupplierAccountsTest):

    def _ops_users(self):
        cur = self._cursor()
        cur.execute("""SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
                       WHERE u.is_active = 1 AND r.code LIKE 'operations_%%' ORDER BY u.id""")
        ids = [r['id'] for r in cur.fetchall()]
        direct = [i for i in ids if not branding_gate._approval_chain(cur, i)]
        below = [i for i in ids if branding_gate._approval_chain(cur, i)]
        return direct, below

    def test_only_direct_to_finance_see_it_on_operations(self):
        direct, below = self._ops_users()
        self.assertTrue(direct and below)
        self.assertIn(b'money-requests', self._web(direct[0]).get('/operation_mainpage').data)
        self.assertNotIn(b'money-requests', self._web(below[0]).get('/operation_mainpage').data)

    def test_not_on_the_main_home_page(self):
        direct, _ = self._ops_users()
        self.assertNotIn(b'money-requests', self._web(direct[0]).get('/home').data)

    def test_owed_paid_and_statement(self): pass
    def test_outsiders_cannot_see_or_pay(self): pass
    def test_bar_on_every_finance_page(self): pass


if __name__ == '__main__':
    unittest.main()
