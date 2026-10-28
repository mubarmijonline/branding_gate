"""
Save draft (Gamal, 2026-10-28): a draft is kept on the server for its author
(and the admin), is not a sales request -- so no list, count, Operation or
Pricing sees it -- and launching it submits the form normally and deletes it.
Rolled back like test_costing.py.
"""

import unittest
from datetime import date, timedelta

import branding_gate
from test_costing import _CostingHarness
import fixtures

SNAPSHOT = {'at': 1, 'types': ['Booth'], 'items': {}, 'values': [{'k': 'title', 'v': 'Gala draft'}]}
PLACE = {'location': 'Nasr City', 'location_governorate': 'Cairo', 'hotel_name': 'Citystars', 'setup_date': 'TBD'}


class SalesDraftsTest(_CostingHarness):

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        cur.execute("SELECT id FROM rbac_role WHERE code = 'admin'")
        self.roles['admin'] = cur.fetchone()['id']
        self.client_id = fixtures.ensure_client(cur)
        cur.close()
        self.seller = self._make_user('draft-seller', 'sales_member', None)
        self.other = self._make_user('draft-other', 'sales_member', None)
        self.admin = self._make_user('draft-admin', 'admin', None)

    def _save(self, who, **extra):
        return self._client_for(who).post('/api/sales/drafts', json=dict({'title': 'Gala', 'snapshot': SNAPSHOT}, **extra))

    def _ids(self, who):
        return [d['id'] for d in self._client_for(who).get('/api/sales/drafts').get_json()['drafts']]

    def _requests(self):
        cur = self._cursor()
        cur.execute("SELECT COUNT(*) AS n FROM sales_request")
        n = cur.fetchone()['n']
        cur.close()
        return n

    def test_only_the_author_and_the_admin_see_it_and_it_is_no_request(self):
        before = self._requests()
        draft = self._save(self.seller).get_json()['id']
        self.assertEqual(self._requests(), before)
        self.assertIn(draft, self._ids(self.seller))
        self.assertNotIn(draft, self._ids(self.other))
        self.assertIn(draft, self._ids(self.admin))
        self.assertEqual(self._client_for(self.other).get('/api/sales/drafts/%d' % draft).status_code, 404)
        self.assertEqual(self._client_for(self.other).delete('/api/sales/drafts/%d' % draft).status_code, 404)
        self.assertEqual(self._save(self.other, id=draft).status_code, 404)
        got = self._client_for(self.seller).get('/api/sales/drafts/%d' % draft).get_json()
        self.assertEqual(got['snapshot']['values'][0]['v'], 'Gala draft')
        self.assertEqual(self._save(self.seller, id=draft, title='Gala 2').get_json()['id'], draft)
        self.assertEqual(self._client_for(self.seller).delete('/api/sales/drafts/%d' % draft).status_code, 200)
        self.assertNotIn(draft, self._ids(self.seller))

    def test_launch_submits_normally_and_deletes_the_draft(self):
        draft = self._save(self.seller).get_json()['id']
        other_draft = self._save(self.other).get_json()['id']
        start = (date.today() + timedelta(days=20)).isoformat()
        payload = {'client_id': self.client_id, 'start_date': start, 'end_date': start, 'title': 'Gala',
                   'request_types': ['Booth'],
                   'template_fields': {'instances': [{'request_type': 'Booth', 'fields': PLACE, 'items': []}]}}
        # Launching still runs every check: no client, no request, draft kept.
        bad = self._client_for(self.seller).post('/api/sales/requests/add', json=dict(
            payload, draft_id=draft, client_id=''))
        self.assertEqual(bad.status_code, 400)
        self.assertIn(draft, self._ids(self.seller))
        r = self._client_for(self.seller).post('/api/sales/requests/add', json=dict(payload, draft_id=draft))
        self.assertTrue(r.get_json().get('success'), r.get_json())
        self.assertNotIn(draft, self._ids(self.seller))
        # Somebody else's draft id does nothing.
        self._client_for(self.seller).post('/api/sales/requests/add', json=dict(payload, draft_id=other_draft))
        self.assertIn(other_draft, self._ids(self.other))

    def test_refuses_empty(self):
        self.assertEqual(self._client_for(self.seller).post('/api/sales/drafts', json={'snapshot': {}}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
