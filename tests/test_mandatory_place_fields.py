"""
Governorate, venue / hotel and setup date (or TBD) are required on a request
(David, 2026-10-28: a request with no governorate was priced as Cairo), on
create and on edit, by the server. Rolled back like test_costing.py.
"""

import json
import unittest
from datetime import date, timedelta

import branding_gate
from test_costing import _CostingHarness
import fixtures

PLACE = {'location': 'Nasr City', 'location_governorate': 'Cairo',
         'hotel_name': 'InterContinental Citystars', 'setup_date': 'TBD'}


class MissingFieldsRuleTest(unittest.TestCase):

    def test_event_types_need_all_four(self):
        miss = branding_gate.missing_request_fields
        self.assertEqual(miss(['Booth'], [{'request_type': 'Booth', 'fields': PLACE}], {}), [])
        self.assertEqual(miss(['Booth'], [{'request_type': 'Booth', 'fields': {'location': 'x'}}], {}),
                         ['Governorate', 'Venue / Hotel Name', 'Setup Date'])
        self.assertEqual(miss(['Booth'], [{'request_type': 'Booth', 'fields': dict(PLACE, setup_date='soon')}], {}),
                         ['Setup Date'])
        self.assertEqual(miss(['Booth'], [{'request_type': 'Booth', 'fields': dict(PLACE, setup_date='2026-11-30')}], {}), [])

    def test_several_types_name_the_type_and_flat_keys_count(self):
        miss = branding_gate.missing_request_fields
        flat = {'Printing_delivery_location': 'Giza warehouse'}
        self.assertEqual(miss(['Booth', 'Printing'], [{'request_type': 'Booth', 'fields': PLACE}], flat),
                         ['Printing: Governorate'])
        self.assertEqual(miss(['Digital marketing'], [], {}), [])


class MandatoryPlaceRoutesTest(_CostingHarness):

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        self.client_id = fixtures.ensure_client(cur)
        cur.close()
        self.seller = self._make_user('place-seller', 'sales_member', None)
        self.start = (date.today() + timedelta(days=20)).isoformat()

    def _payload(self, fields):
        return {'client_id': self.client_id, 'start_date': self.start, 'end_date': self.start,
                'request_types': ['Booth'], 'title': 'Place test',
                'template_fields': {'instances': [{'request_type': 'Booth', 'instance_id': '1_Booth',
                                                   'fields': fields, 'items': []}],
                                    'flat_fields': {'Booth_' + k: v for k, v in fields.items()}}}

    def test_create_refuses_without_governorate_and_accepts_with(self):
        web = self._client_for(self.seller)
        r = web.post('/api/sales/requests/add', json=self._payload({'location': 'Nasr City'}))
        self.assertEqual(r.status_code, 400)
        self.assertIn('Governorate', r.get_json()['missing'])
        r = web.post('/api/sales/requests/add', json=self._payload(PLACE))
        self.assertTrue(r.get_json().get('success'), r.get_json())

    def test_edit_refuses_without_venue(self):
        # What the edit form sends: JSON, the same instances as on create.
        body = self._payload(dict(PLACE, hotel_name=''))
        r = self._client_for(self.head).post('/api/sales-requests/update-with-template/%d' % self.request_id, json=body)
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True)[:300])
        self.assertEqual(r.get_json()['missing'], ['Venue / Hotel Name'])
        r = self._client_for(self.head).post('/api/sales-requests/update-with-template/%d' % self.request_id,
                                             json=self._payload(PLACE))
        self.assertTrue(r.get_json().get('success'), r.get_json())

if __name__ == '__main__':
    unittest.main()
