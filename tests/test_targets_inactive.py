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


if __name__ == '__main__':
    unittest.main()
