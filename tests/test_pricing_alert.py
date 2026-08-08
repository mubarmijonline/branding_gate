"""
What the sales request list says is waiting for a price.

The banner and the row mark on /sales_request are both counted from
approval_stats.not_priced in /api/sales/requests, so this pins that number to
what the items table actually holds. Read-only.
"""

import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate


def _connect():
    return MySQLdb.connect(
        host="localhost", user="ps", passwd="Aa@123456", db="branding_gate",
        port=3306, charset="utf8mb4", use_unicode=True,
        cursorclass=MySQLdb.cursors.DictCursor,
    )


class NotPricedCountTest(unittest.TestCase):
    """Costed, no price yet -- the state costing hands to pricing."""

    @classmethod
    def setUpClass(cls):
        perms, role_code = branding_gate.load_permissions(1)
        cls.client = branding_gate.app.test_client()
        with cls.client.session_transaction() as flask_session:
            flask_session.update({
                "user_id": 1, "mobile": "m", "email": "e",
                "username": "u", "name": "n",
                "roles": [role_code], "perms": perms, "role_code": role_code,
            })

    def _expected(self):
        conn = _connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT request_id, COUNT(*) AS n
            FROM sales_request_items
            WHERE cost_per_item IS NOT NULL AND sell_per_item IS NULL
            GROUP BY request_id
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {row['request_id']: row['n'] for row in rows}

    def test_the_list_reports_every_item_waiting_for_a_price(self):
        response = self.client.get('/api/sales/requests')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload.get('success'), payload)

        expected = self._expected()
        for request in payload['requests']:
            self.assertEqual(
                request['approval_stats']['not_priced'],
                expected.get(request['request_id'], 0),
                'request %s' % request['request_id'],
            )

    def test_an_uncosted_item_is_not_counted_as_waiting_for_a_price(self):
        # The two ends of the handover must not both claim the same item, or
        # the banner counts work that costing has not finished yet.
        response = self.client.get('/api/sales/requests')
        payload = response.get_json()
        conn = _connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT request_id, COUNT(*) AS n FROM sales_request_items
            WHERE cost_per_item IS NULL GROUP BY request_id
        """)
        uncosted = {row['request_id']: row['n'] for row in cur.fetchall()}
        cur.close()
        conn.close()
        for request in payload['requests']:
            stats = request['approval_stats']
            self.assertEqual(stats['not_costed'],
                             uncosted.get(request['request_id'], 0),
                             'request %s' % request['request_id'])


class PricingSummaryTest(unittest.TestCase):
    """The number on the Pricing menu."""

    def _client_for(self, user_id):
        perms, role_code = branding_gate.load_permissions(user_id)
        client = branding_gate.app.test_client()
        with client.session_transaction() as flask_session:
            flask_session.update({
                "user_id": user_id, "mobile": "m", "email": "e",
                "username": "u", "name": "n",
                "roles": [role_code], "perms": perms, "role_code": role_code,
            })
        return client

    def _a_user_holding(self, role_code):
        conn = _connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.id FROM user u
            JOIN rbac_role r ON r.id = u.rbac_role_id
            WHERE r.code = %s ORDER BY u.id LIMIT 1
        """, (role_code,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row['id'] if row else None

    def test_the_totals_are_what_the_items_table_holds(self):
        payload = self._client_for(1).get('/api/pricing/summary').get_json()
        self.assertTrue(payload.get('success'), payload)

        conn = _connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(CASE WHEN cost_per_item IS NOT NULL
                               AND sell_per_item IS NULL THEN 1 END) AS to_price,
                   COUNT(CASE WHEN approval_status = 'pending_negotiation'
                               AND negotiation_status = 'negotiated' THEN 1 END) AS to_reprice
            FROM sales_request_items
        """)
        expected = cur.fetchone()
        cur.close()
        conn.close()

        self.assertEqual(payload['to_price_total'], expected['to_price'])
        self.assertEqual(payload['to_reprice_total'], expected['to_reprice'])

    def test_only_a_request_with_work_on_it_is_listed(self):
        payload = self._client_for(1).get('/api/pricing/summary').get_json()
        for request_id, counts in payload['by_request'].items():
            self.assertTrue(counts['to_price'] or counts['to_reprice'], request_id)

    def test_somebody_who_does_not_price_is_refused(self):
        # The badge is Pricing's; a sales member must not be able to read the
        # whole company's pricing backlog through it.
        user_id = self._a_user_holding('sales_member')
        if user_id is None:
            self.skipTest('no sales member in this database')
        self.assertEqual(
            self._client_for(user_id).get('/api/pricing/summary').status_code, 403)


if __name__ == '__main__':
    unittest.main()
