"""
Client Approval page: who created each request, and a filter on it
(Ahmed, 2026-11-02). created_by holds a mobile on this request, as it does
on most; the page gets the person behind it. Rolled back like test_costing.py.
"""

import unittest

from test_costing import _CostingHarness


class CreatedByTest(_CostingHarness):

    def test_items_carry_the_creator_and_filter_on_them(self):
        creator = self._make_user('ca-creator', 'sales_member', None)
        cur = self._cursor()
        cur.execute("SELECT mobile, name FROM user WHERE id = %s", (creator,))
        person = cur.fetchone()
        cur.execute("UPDATE sales_request SET created_by = %s WHERE id = %s", (person['mobile'], self.request_id))
        cur.execute("SELECT client_id FROM sales_request WHERE id = %s", (self.request_id,))
        client = cur.fetchone()['client_id']
        cur.execute("SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id "
                    "WHERE r.code = 'admin' AND u.is_active = 1 LIMIT 1")
        admin = cur.fetchone()['id']
        cur.close()
        web = self._client_for(admin)

        body = web.get('/api/client-approval/items?client=%s' % client).get_json()
        mine = [i for i in body['items'] if i['request_id'] == self.request_id]
        self.assertEqual(mine[0]['created_by_name'], person['name'])
        self.assertNotIn('sales_added_by', mine[0])
        self.assertIn({'id': creator, 'name': person['name']}, body['creators'])

        only = web.get('/api/client-approval/items?client=%s&created_by=%d' % (client, creator)).get_json()['items']
        self.assertTrue(only)
        self.assertEqual({i['created_by_user_id'] for i in only}, {creator})
        none = web.get('/api/client-approval/items?client=%s&created_by=999999999' % client).get_json()['items']
        self.assertEqual(none, [])


if __name__ == '__main__':
    unittest.main()
