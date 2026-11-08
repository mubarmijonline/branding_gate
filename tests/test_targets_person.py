"""
One person's target report (Gamal, 2026-11-08): where the target came from,
the month split, the team, and every request behind the number. Its approved
total is the table's Achieved, by the same rule. Rolled back like
test_costing.py.
"""

import testdb  # noqa: F401  first: the test database, not the live one
import unittest

import branding_gate
from test_costing import _CostingHarness


class TargetPersonTest(_CostingHarness):

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        cur.execute("SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id "
                    "WHERE r.code = 'admin' AND u.is_active = 1 LIMIT 1")
        self.admin = cur.fetchone()['id']
        cur.execute("SELECT client_id FROM sales_request WHERE id = %s", (self.request_id,))
        self.client_id = cur.fetchone()['client_id']
        cur.close()
        self.web = self._client_for(self.admin)
        self.period = branding_gate.targets_lib.current_period()
        for user, amount in ((self.head, '10000'), (self.leader, '6000'), (self.member, '2000')):
            r = self.web.post('/api/targets/assign', json={'user_id': user, 'period': self.period,
                                                          'amount': amount, 'note': 'q plan'})
            self.assertEqual(r.status_code, 200, r.get_json())

    def _request(self, owner, *items):
        cur = self._cursor()
        cur.execute("INSERT INTO sales_request (client_id, title, start_date, created_by, owner_user_id) "
                    "VALUES (%s, 'tgt', CURDATE(), 'tgt', %s)", (self.client_id, owner))
        request_id = cur.lastrowid
        for status, sell in items:
            cur.execute("INSERT INTO sales_request_items (request_id, name, qty, approval_status, "
                        "sell_per_item, total_sell) VALUES (%s, 'i', 1, %s, %s, %s)",
                        (request_id, status, sell, sell))
        cur.close()
        return request_id

    def _report(self, user_id, viewer=None):
        client = self._client_for(viewer) if viewer else self.web
        return client.get('/api/targets/person?period=%s&user_id=%d' % (self.period, user_id))

    def test_the_report_adds_up_to_the_table(self):
        mine = self._request(self.leader, ('approved', 1000), ('pending', 400))
        theirs = self._request(self.member, ('approved', 250), ('rejected', 99), ('pending', None))
        body = self._report(self.leader).get_json()
        self.assertTrue(body['success'], body)

        row = [r for r in self.web.get('/api/targets?period=' + self.period).get_json()['rows']
               if r['id'] == self.leader][0]
        self.assertEqual(sum(r['approved'] for r in body['requests']), row['team_achieved'])
        self.assertEqual(body['target']['team_achieved'], 1250)
        self.assertEqual(body['target']['own_achieved'], 1000)
        self.assertEqual(sum(m['achieved'] for m in body['months']), 1250)

        by_id = {r['id']: r for r in body['requests']}
        self.assertEqual(set(by_id), {mine, theirs})
        self.assertEqual((by_id[mine]['waiting'], by_id[theirs]['rejected'], by_id[theirs]['unpriced']),
                         (400, 99, 1))
        # Stage is read off the items, not the stored copy on the request.
        self.assertEqual((by_id[mine]['stage'], by_id[theirs]['stage']), ('partially_approved', 'partially_approved'))
        self.assertEqual(branding_gate._request_stage({'approved': 5, 'waiting': 0, 'rejected': 0, 'unpriced': 0,
                                                       'uncosted': 0, 'items': 1}), 'approved')
        self.assertEqual(branding_gate._request_stage({'approved': 0, 'waiting': 9, 'rejected': 0, 'unpriced': 0,
                                                       'uncosted': 0, 'items': 1}), 'pending')
        self.assertEqual(branding_gate._request_stage({'approved': 0, 'waiting': 0, 'rejected': 3, 'unpriced': 0,
                                                       'uncosted': 0, 'items': 1}), 'rejected')
        self.assertEqual(sorted(m['id'] for m in body['team']), sorted([self.member, self.member_b]))
        self.assertEqual(sum(c['approved'] for c in body['clients']), 1250)
        quarter = [q for q in body['year'] if q['period'] == self.period][0]
        self.assertEqual((quarter['target'], quarter['achieved']), (6000, 1250))

    def test_the_target_path_names_every_step(self):
        body = self._report(self.member).get_json()
        steps = [(s['id'], s['target'], s.get('share')) for s in body['path']]
        self.assertEqual(steps[-3:], [(self.head, 10000, None), (self.leader, 6000, 60.0), (self.member, 2000, 33.3)])
        self.assertEqual(body['path'][-1]['note'], 'q plan')
        self.assertIsNotNone(body['path'][-1]['set_by'])

    def test_outside_your_scope_is_refused(self):
        self.assertEqual(self._report(self.leader, viewer=self.member).status_code, 403)
        own = self._report(self.member, viewer=self.member).get_json()
        # A member sees their own report, but not the targets above them.
        self.assertEqual([s['id'] for s in own['path']], [self.member])
        self.assertEqual(self._client_for(self.member).get('/targets/person/%d' % self.leader).status_code, 403)
        self.assertEqual(self.web.get('/targets/person/%d' % self.leader).status_code, 200)


if __name__ == '__main__':
    unittest.main()
