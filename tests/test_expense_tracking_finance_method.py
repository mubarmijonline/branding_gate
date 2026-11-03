"""
Finance, not the requester, chooses the payment method (Ahmed, 2026-11-03).

The Expense Tracking form no longer asks the requester for one; Finance picks
it when approving, and the transactions go through that method. Rollback-based.
"""

import testdb  # noqa: F401  first: the test database, not the live one
import unittest

from test_supplier_accounts import SupplierAccountsTest


class ExpenseTrackingFinanceMethodTest(SupplierAccountsTest):

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        cur.execute("SELECT id FROM finance_categories WHERE account_code = '6212'")
        self.account = cur.fetchone()['id']
        cur.execute("""INSERT INTO expense_tracking (tracking_code, user_id, total_amount, tracking_date, status)
                       VALUES ('TRK-T1', %s, 300, '2026-11-03', 'manager_approved')""", (self.outsider,))
        self.tracking = cur.lastrowid
        cur.execute("""INSERT INTO expense_tracking_items (tracking_id, sales_request_id, item_description, amount)
                       VALUES (%s, %s, 'Uber', 300)""", (self.tracking, self.sr))
        self.item = cur.lastrowid

    def _approve(self, **extra):
        return self._web(self.finance).post('/api/expense-tracking/%d/finance-approve' % self.tracking, json=dict(
            items=[{'item_id': self.item, 'category_id': self.account}], **extra))

    def test_finance_must_choose_the_method(self):
        r = self._approve()
        self.assertEqual(r.status_code, 400)
        self.assertIn('payment method', r.get_json()['error'])

    def test_the_chosen_method_is_used(self):
        r = self._approve(payment_method_id=self.pm)
        self.assertEqual(r.status_code, 200, r.get_json())
        cur = self._cursor()
        cur.execute("SELECT payment_method_id, status FROM expense_tracking WHERE id = %s", (self.tracking,))
        self.assertEqual(cur.fetchone(), {'payment_method_id': self.pm, 'status': 'approved'})
        cur.execute("""SELECT DISTINCT payment_method_id FROM finance_transactions
                       WHERE description LIKE %s OR notes LIKE %s""", ('%TRK-T1%', '%TRK-T1%'))
        self.assertEqual([r['payment_method_id'] for r in cur.fetchall()], [self.pm])

    def test_owed_paid_and_statement(self): pass
    def test_outsiders_cannot_see_or_pay(self): pass
    def test_bar_on_every_finance_page(self): pass


if __name__ == '__main__':
    unittest.main()
