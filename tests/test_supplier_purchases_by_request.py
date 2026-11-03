"""
Paying supplier purchases by request (George / Ahmed, 2026-11-03).

What an SR owes a supplier is the cost of its client-approved items with that
supplier, less the supplier payments booked against that SR. Finance pays it
from a payment method chosen on the request; the payment posts Dr 2101 and Cr
the method's account: a cash method on 1101, a bank one on 1102. Rollback-based.
"""

import testdb  # noqa: F401  first: the test database, not the live one
import unittest

import branding_gate
from test_supplier_accounts import SupplierAccountsTest


class SupplierPurchasesByRequestTest(SupplierAccountsTest):

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        cur.execute("""INSERT INTO payment_methods (method_name, method_code, method_type, current_balance)
                       VALUES ('Sup Bank T', 'SUP_BANK_T', 'bank', 50000)""")
        self.bank = cur.lastrowid

    def _row(self, web):
        r = web.get('/api/finance/supplier-purchases?supplier_id=%d' % self.supplier)
        self.assertEqual(r.status_code, 200)
        rows = [x for x in r.get_json()['rows'] if x['sales_request_id'] == self.sr]
        self.assertEqual(len(rows), 1)
        return rows[0]

    def _journal(self, trans_id):
        cur = self._cursor()
        lines = [l for l in branding_gate.chart_journal(cur) if l['source'] == ('txn', trans_id)]
        return sorted((l['account'], l['debit'], l['credit'], l['method']) for l in lines)

    def test_owed_by_request_and_paid_from_the_chosen_method(self):
        finance = self._web(self.finance)
        row = self._row(finance)
        # Only the approved item is owed; the pending one is not.
        self.assertEqual((row['purchased'], row['paid'], row['remaining']), (10000.0, 0.0, 10000.0))
        self.assertEqual([i['cost'] for i in row['items']], [10000.0])

        url = '/api/finance/supplier-accounts/%d/payment' % self.supplier
        cash = finance.post(url, json={'amount': 3000, 'payment_method_id': self.pm, 'sales_request_id': self.sr})
        self.assertEqual(cash.status_code, 200, cash.get_json())
        bank = finance.post(url, json={'amount': 7000, 'payment_method_id': self.bank, 'sales_request_id': self.sr})
        self.assertEqual(bank.status_code, 200, bank.get_json())
        self.assertEqual(self._journal(cash.get_json()['transaction_id']),
                         [('1101', 0.0, 3000.0, self.pm), ('2101', 3000.0, 0.0, None)])
        self.assertEqual(self._journal(bank.get_json()['transaction_id']),
                         [('1102', 0.0, 7000.0, self.bank), ('2101', 7000.0, 0.0, None)])
        self.assertEqual(self._row(finance)['remaining'], 0.0)

        # Nothing left on the request: more is refused, and no money moves.
        r = finance.post(url, json={'amount': 1, 'payment_method_id': self.pm, 'sales_request_id': self.sr})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self._balance(), 47000.0)
        # Without an SR it is a payment on account, as before.
        self.assertEqual(finance.post(url, json={'amount': 1, 'payment_method_id': self.pm}).status_code, 200)

    def test_outsiders_cannot_list_purchases(self):
        r = self._web(self.outsider).get('/api/finance/supplier-purchases')
        self.assertIn(r.status_code, (302, 403))

    # The inherited tests already ran in test_supplier_accounts.
    def test_owed_paid_and_statement(self): pass
    def test_outsiders_cannot_see_or_pay(self): pass
    def test_bar_on_every_finance_page(self): pass


if __name__ == '__main__':
    unittest.main()
