"""
Company is optional on the New Request form, which sends '' when none is
picked; that '' went into an INT column and MySQL refused the whole request
(1366). Rolled back like test_costing.py.
"""

import unittest
from datetime import date, timedelta

from test_costing import _CostingHarness


class AddRequestWithoutCompanyTest(_CostingHarness):

    def test_empty_company_is_saved_as_none(self):
        cur = self._cursor()
        cur.execute("SELECT client_id FROM sales_request WHERE id = %s", (self.request_id,))
        client_id = cur.fetchone()['client_id']
        seller = self._make_user('add-seller', 'sales_member', None)
        response = self._client_for(seller).post('/api/sales/requests/add', json={
            'client_id': client_id, 'company_id': '', 'title': 'No company request',
            'priority': 'normal', 'start_date': (date.today() + timedelta(days=30)).isoformat(),
            'request_types': ['Others'],
            # The place fields every request needs now (David, 2026-10-28).
            'template_fields': {'instances': [{'request_type': 'Others', 'items': [],
                                               'fields': {'location': 'Maadi', 'location_governorate': 'Cairo'}}]},
            'items': [{'name': 'Banner', 'quantity': 2, 'unit': 'pcs'}]})
        body = response.get_json()
        self.assertTrue(body.get('success'), body)
        if body.get('request_id'):
            cur.execute("SELECT company_id FROM sales_request WHERE id = %s", (body['request_id'],))
            self.assertIsNone(cur.fetchone()['company_id'])


if __name__ == '__main__':
    unittest.main()
