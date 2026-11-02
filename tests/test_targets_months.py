"""
Targets by month and what makes up Achieved (Gamal, 2026-11-02): a quarter's
target may be spread unevenly over its months but always adds up to the
quarter, and clicking Achieved lists the client-approved requests behind it,
for the person and the team under them. Rolled back like test_costing.py.
"""

import unittest

import branding_gate
from test_costing import _CostingHarness


class TargetMonthsTest(_CostingHarness):

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        cur.execute("SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id "
                    "WHERE r.code = 'admin' AND u.is_active = 1 LIMIT 1")
        self.admin = cur.fetchone()['id']
        cur.close()
        self.web = self._client_for(self.admin)
        self.period = branding_gate.targets_lib.current_period()

    def test_the_months_must_add_up_to_the_quarter(self):
        seller = self._make_user('tgt-month', 'sales_member', self.head)
        bad = self.web.post('/api/targets/assign', json={'user_id': seller, 'period': self.period,
                                                        'amount': '900', 'months': ['100', '200', '300']})
        self.assertEqual(bad.status_code, 400)
        ok = self.web.post('/api/targets/assign', json={'user_id': seller, 'period': self.period,
                                                       'amount': '900', 'months': ['100', '300', '500']})
        self.assertEqual(ok.status_code, 200, ok.get_json())
        row = [r for r in self.web.get('/api/targets?period=' + self.period).get_json()['rows'] if r['id'] == seller][0]
        self.assertEqual([m['target'] for m in row['months']], [100, 300, 500])
        # Changing the amount without a split goes back to an even one.
        self.web.post('/api/targets/assign', json={'user_id': seller, 'period': self.period, 'amount': '300'})
        row = [r for r in self.web.get('/api/targets?period=' + self.period).get_json()['rows'] if r['id'] == seller][0]
        self.assertEqual([m['target'] for m in row['months']], [100, 100, 100])

    def test_achieved_lists_the_approved_requests_of_the_team(self):
        leader = self._make_user('tgt-lead', 'sales_member', self.head)
        member = self._make_user('tgt-member', 'sales_member', leader)
        cur = self._cursor()
        cur.execute("SELECT client_id FROM sales_request WHERE id = %s", (self.request_id,))
        client_id = cur.fetchone()['client_id']
        made = []
        for owner, status, sell in ((leader, 'approved', 1000), (member, 'approved', 250), (member, 'rejected', 99)):
            cur.execute("INSERT INTO sales_request (client_id, title, start_date, created_by, owner_user_id) "
                        "VALUES (%s, 'tgt', CURDATE(), 'tgt', %s)", (client_id, owner))
            made.append(cur.lastrowid)
            cur.execute("INSERT INTO sales_request_items (request_id, name, qty, approval_status, total_sell) "
                        "VALUES (%s, 'i', 1, %s, %s)", (cur.lastrowid, status, sell))
        cur.close()
        body = self.web.get('/api/targets/achieved?period=%s&user_id=%d' % (self.period, leader)).get_json()
        self.assertEqual(sorted(r['id'] for r in body['requests']), made[:2])
        self.assertEqual(sum(m['achieved'] for m in body['months']), 1250)
        row = [r for r in self.web.get('/api/targets?period=' + self.period).get_json()['rows'] if r['id'] == leader][0]
        self.assertEqual(row['team_achieved'], 1250)
        self.assertEqual(sum(m['achieved'] for m in row['months']), 1250)
        mine = self.web.get('/api/targets/achieved?period=%s&user_id=%d' % (self.period, member)).get_json()
        self.assertEqual([r['id'] for r in mine['requests']], [made[1]])


if __name__ == '__main__':
    unittest.main()
