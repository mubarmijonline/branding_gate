"""
Account Management and Sales never receive cost, profit or margin from the
sales-side APIs, whatever the page: one guard (hide_cost_from_sales) strips it
for whoever may not see cost (Gamal, 2026-10-29). Operations, Pricing, Finance
and the admin still get it. Rolled back like test_costing.py.
"""

import json
import unittest

import branding_gate
from test_costing import _CostingHarness

COST = lambda keys: [k for k in keys if branding_gate.COST_KEY.search(k)
                     and not branding_gate.COST_KEY_KEEP.search(k)]


def money_keys(value, out=None):
    out = set() if out is None else out
    if isinstance(value, dict):
        out.update(COST(value.keys()))
        for v in value.values():
            money_keys(v, out)
    elif isinstance(value, list):
        for v in value:
            money_keys(v, out)
    return out


class ScrubTest(unittest.TestCase):

    def test_keys_and_cost_log_entries_go(self):
        out = branding_gate.scrub_cost({
            'total_cost': 5, 'costed_items_count': 2, 'approval_stats_not_costed': 1, 'total_sell': 9,
            'items': [{'cost_per_item': 1, 'profit_margin': 3, 'name': 'x'}],
            'change_log': [{'action_type': 'COST_UPDATE', 'change_description': 'cost 100 -> 200'},
                           {'action_type': 'CREATE', 'change_description': "created for client 'Costa Coffee'"}]})
        self.assertEqual(out['items'], [{'name': 'x'}])
        self.assertNotIn('total_cost', out)
        self.assertEqual((out['costed_items_count'], out['approval_stats_not_costed'], out['total_sell']), (2, 1, 9))
        self.assertEqual([e['action_type'] for e in out['change_log']], ['CREATE'])


class CostHiddenFromAccountTest(_CostingHarness):

    URLS = ('/api/sales/requests/%d', '/api/sales/requests', '/api/workflow/request/%d/timeline',
            '/api/sales/requests/%d/items', '/api/sales/requests/%d/approval-stage')

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        cur.execute("SELECT id FROM rbac_role WHERE code = 'account_team_leader'")
        self.roles['account_team_leader'] = cur.fetchone()['id']
        self.account = self._make_user('cost-account-tl', 'account_team_leader', None)
        cur.execute("UPDATE sales_request SET owner_user_id = %s, total_cost = 12345 WHERE id = %s",
                    (self.account, self.request_id))
        cur.execute("UPDATE sales_request_items SET cost_per_item = 3086, total_cost = 12345 WHERE id = %s",
                    (self.item_id,))
        cur.close()

    def _get(self, user, url):
        return self._client_for(user).get(url % self.request_id if '%d' in url else url)

    def test_account_level_gets_no_cost(self):
        for url in self.URLS:
            with self.subTest(url=url):
                response = self._get(self.account, url)
                self.assertEqual(response.status_code, 200, url)
                body = response.get_json()
                self.assertEqual(money_keys(body), set(), url)
                self.assertNotIn('12345', json.dumps(body))
                self.assertNotIn('3086', json.dumps(body))

    def test_operations_still_sees_cost(self):
        body = self._get(self.head, '/api/sales/requests/%d').get_json()
        self.assertIn('12345', json.dumps(body))


if __name__ == '__main__':
    unittest.main()
