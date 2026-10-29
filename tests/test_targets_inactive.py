"""
The targets tree leaves out switched-off accounts with nothing to show
(Gamal, 2026-10-28: a placeholder "Account Team Leader 2" card beside Sarah),
but keeps an inactive person who had a target. Rolled back like test_costing.py.
"""

import unittest

import branding_gate
from test_costing import _CostingHarness


class TargetsInactiveTest(_CostingHarness):

    def test_inactive_without_numbers_is_left_out(self):
        placeholder = self._make_user('tgt-placeholder', 'sales_member', self.head)
        left = self._make_user('tgt-left', 'sales_member', self.head)
        cur = self._cursor()
        cur.execute("UPDATE user SET is_active = 0 WHERE id IN (%s, %s)", (placeholder, left))
        cur.execute("INSERT INTO sales_target (user_id, period, amount, assigned_by) VALUES (%s, '2026-Q4', 1000, %s)",
                    (left, self.head))
        ids = {p['id'] for p in branding_gate._target_people(cur)}
        cur.close()
        self.assertNotIn(placeholder, ids)
        self.assertIn(left, ids)
        self.assertIn(self.head, ids)

    def test_only_client_approved_items_count_toward_the_target(self):
        # Gamal, 2026-10-30: Mariam's target counted a request the client rejected.
        seller = self._make_user('tgt-seller', 'sales_member', self.head)
        cur = self._cursor()
        cur.execute("SELECT client_id FROM sales_request WHERE id = %s", (self.request_id,))
        client_id = cur.fetchone()['client_id']

        def request(items, **cols):
            cur.execute("INSERT INTO sales_request (client_id, title, start_date, created_by, owner_user_id) "
                        "VALUES (%s, 'tgt', CURDATE(), 'tgt', %s)", (client_id, seller))
            rid = cur.lastrowid
            for k, v in cols.items():
                cur.execute("UPDATE sales_request SET " + k + " = %s WHERE id = %s", (v, rid))
            for status, sell in items:
                cur.execute("INSERT INTO sales_request_items (request_id, name, qty, approval_status, total_sell) "
                            "VALUES (%s, 'i', 1, %s, %s)", (rid, status, sell))

        request([('approved', 1000), ('rejected', 500), ('pending', 300)])
        request([('rejected', 17330)])
        request([('approved', 400)], status='cancelled')
        request([('approved', 200)], approval_status='rejected')
        period = branding_gate.targets_lib.current_period()
        achieved = branding_gate._target_achieved(cur, period)
        year = int(period[:4])
        by_quarter = branding_gate._target_achieved_by_quarter(cur, year)
        cur.close()
        self.assertEqual(achieved.get(seller), 1000)
        self.assertEqual(by_quarter[period].get(seller), 1000)


if __name__ == '__main__':
    unittest.main()
