"""
Past approvals on /approvals (Ahmed for Beshoy, 2026-10-29): the history lists
decided requests newest first with who decided, when and why, names the client
and company the JSON only holds ids for, filters by outcome and searches title,
client and requester. Approvers only. Rolled back like test_costing.py.
"""

import json
import unittest

from test_costing import _CostingHarness


class ApprovalsHistoryTest(_CostingHarness):

    def setUp(self):
        super().setUp()
        try:
            self._fixtures()
        except Exception:
            # A failed setUp skips tearDown; roll back here or the open
            # transaction holds its row locks against every other run.
            super().tearDown()
            raise

    def _fixtures(self):
        cur = self._cursor()
        cur.execute("SELECT id FROM rbac_role WHERE code = 'sales_head'")
        self.roles['sales_head'] = cur.fetchone()['id']
        self.approver = self._make_user('hist-approver', 'sales_head', None)
        self.requester = self._make_user('hist-requester', 'sales_member', None)
        cur.execute("INSERT INTO client (client_name, mobile_number, email_address, added_by) "
                    "VALUES ('Zebra Pharma Hist', '01000000099', 'z@example.com', 'test')")
        self.client_id = cur.lastrowid
        cur.execute("""INSERT INTO company (company_name, industry_sector, address, email_address, phone_number,
                                            primary_contact_person, added_by)
                       VALUES ('Hist Holding Co', 'Pharma', 'Cairo', 'h@example.com', '0200000000', 'Nobody', 'test')""")
        self.company_id = cur.lastrowid

        def approval(title, status, **cols):
            data = {'title': title, 'client_id': str(self.client_id), 'company_id': str(self.company_id),
                    'start_date': '2026-11-01', 'request_types': ['Printing'], 'template_fields': {}}
            cur.execute("""INSERT INTO sales_request_approvals
                           (request_data, requested_by, status, reviewed_by, reviewed_at,
                            notes, rejection_reason, sales_request_id)
                           VALUES (%s, 'hist-requester', %s, %s, %s, %s, %s, %s)""",
                        (json.dumps(data), status, cols.get('by'), cols.get('at'), cols.get('notes'),
                         cols.get('reason'), cols.get('sr')))
            return cur.lastrowid
        self.pending = approval("Hist pending 'quoted'", 'pending')
        self.approved = approval('Hist booth approved', 'approved', by='hist-approver',
                                 at='2037-01-02 10:00:00', notes='Fine, go ahead', sr=self.request_id)
        self.rejected = approval('Hist stand rejected', 'rejected', by='hist-approver',
                                 at='2037-01-03 10:00:00', reason='Too late to produce')
        cur.close()

    def _history(self, query=''):
        r = self._client_for(self.approver).get('/api/approvals/history?limit=100' + query)
        self.assertEqual(r.status_code, 200, r.get_json())
        return r.get_json()

    def test_history_lists_decisions_with_reviewer_reason_and_names(self):
        rows = self._history()['approvals']
        ids = [a['id'] for a in rows]
        self.assertNotIn(self.pending, ids)
        # Newest decision first (the fixtures are dated in 2037 to sort on top).
        self.assertEqual(ids[:2], [self.rejected, self.approved])
        approved = rows[1]
        self.assertEqual(approved['reviewed_by_name'], 'hist-approver')
        self.assertEqual(approved['requested_by_name'], 'hist-requester')
        self.assertTrue(approved['requested_by_mobile'])
        self.assertEqual(approved['notes'], 'Fine, go ahead')
        self.assertEqual(approved['sales_request_id'], self.request_id)
        self.assertEqual(approved['reviewed_at'], '2037-01-02 10:00:00')
        self.assertEqual((approved['client_name'], approved['company_name']), ('Zebra Pharma Hist', 'Hist Holding Co'))
        self.assertEqual(rows[0]['rejection_reason'], 'Too late to produce')
        self.assertEqual(rows[0]['thread_count'], 0)

    def test_filter_search_and_paging(self):
        only = lambda q: [a['id'] for a in self._history(q)['approvals']]
        self.assertIn(self.approved, only('&status=approved'))
        self.assertNotIn(self.rejected, only('&status=approved'))
        self.assertEqual(only('&status=rejected&q=hist'), [self.rejected])
        self.assertEqual(only('&q=BOOTH'), [self.approved])                     # title, any case
        self.assertEqual(set(only('&q=zebra pharma')), {self.approved, self.rejected})   # client name
        self.assertEqual(set(only('&q=hist-requester')), {self.approved, self.rejected})  # requester
        self.assertEqual(only('&q=nothing-matches-this'), [])
        page = self._client_for(self.approver).get('/api/approvals/history?limit=1&q=hist').get_json()
        self.assertEqual(([a['id'] for a in page['approvals']], page['has_more']), ([self.rejected], True))
        page = self._client_for(self.approver).get('/api/approvals/history?limit=1&offset=1&q=hist').get_json()
        self.assertEqual(([a['id'] for a in page['approvals']], page['has_more']), ([self.approved], False))
        self.assertEqual(self._client_for(self.approver).get('/api/approvals/history?limit=x').status_code, 400)

    def test_only_approvers(self):
        for path in ('/api/approvals/history', '/api/approvals/pending'):
            self.assertEqual(self._client_for(self.requester).get(path).status_code, 403, path)

    def test_pending_cards_carry_resolved_names(self):
        r = self._client_for(self.approver).get('/api/approvals/pending').get_json()
        card = [a for a in r['approvals'] if a['id'] == self.pending][0]
        self.assertEqual((card['client_name'], card['company_name']), ('Zebra Pharma Hist', 'Hist Holding Co'))
        self.assertEqual(card['requested_by_name'], 'hist-requester')
        self.assertEqual(card['request_data']['title'], "Hist pending 'quoted'")

    def test_page_passes_titles_by_id_not_inside_onclick(self):
        page = self._client_for(self.approver).get('/approvals').data.decode()
        self.assertIn('Past approvals', page)
        self.assertNotIn("approveRequest(${", page)
        self.assertIn("$(this).data('id')", page)


if __name__ == '__main__':
    unittest.main()
