import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate
import fixtures
import rbac


class _RollbackConnection:
    def __init__(self, raw_connection):
        self.raw_connection = raw_connection

    def commit(self):
        pass

    def close(self):
        pass

    def rollback(self):
        self.raw_connection.rollback()


class NegotiationRouteTest(unittest.TestCase):
    def setUp(self):
        self.raw_connection = MySQLdb.connect(
            host="localhost",
            user="ps",
            passwd="Aa@123456",
            db="branding_gate",
            port=3306,
            charset="utf8mb4",
            use_unicode=True,
        )
        self.raw_connection.autocommit(False)
        self.connection_wrapper = _RollbackConnection(self.raw_connection)
        self.original_connection = branding_gate.connection
        branding_gate.connection = self._connection

        cursor = self._cursor()
        cursor.execute("SELECT id FROM client ORDER BY id LIMIT 1")
        client_id = cursor.fetchone()["id"]
        cursor.execute(
            """
            INSERT INTO sales_request
                (client_id, title, start_date, created_by, items_count)
            VALUES (%s, 'Negotiation workflow test', CURDATE(), 'Automated Test', 2)
            """,
            (client_id,),
        )
        self.request_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO sales_request_items
                (request_id, name, qty, unit, cost_per_item, sell_per_item,
                 total_cost, total_sell, approval_status, negotiation_status,
                 negotiation_reason, negotiation_count, sell_type)
            VALUES
                (%s, 'Negotiated test item', 1, 'pcs', 100, 160,
                 100, 160, 'pending_negotiation', 'pending_negotiation',
                 'Client requested a lower price', 1, 'sell')
            """,
            (self.request_id,),
        )
        self.item_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO sales_request_items
                (request_id, name, qty, unit, approval_status, negotiation_status)
            VALUES (%s, 'Uncosted control item', 1, 'pcs', 'pending', 'none')
            """,
            (self.request_id,),
        )
        cursor.execute(
            """
            INSERT INTO negotiation_requests
                (item_id, request_id, client_expected_price, client_reason,
                 status, sales_head_decision)
            VALUES (%s, %s, 140, 'Client requested a lower price',
                    'pending_sales_head', 'pending')
            """,
            (self.item_id, self.request_id),
        )
        self.negotiation_id = cursor.lastrowid
        cursor.close()

    def tearDown(self):
        branding_gate.connection = self.original_connection
        self.raw_connection.rollback()
        self.raw_connection.close()

    def _cursor(self):
        return self.raw_connection.cursor(MySQLdb.cursors.DictCursor)

    def _connection(self):
        return self.connection_wrapper, self._cursor()

    def _set_negotiation_state(self, status, destination=None):
        cursor = self._cursor()
        cursor.execute(
            """
            UPDATE negotiation_requests
            SET status = %s, destination_team = %s,
                sales_head_decision = IF(%s = 'pending_sales_head', 'pending', 'approved')
            WHERE id = %s
            """,
            (status, destination, status, self.negotiation_id),
        )
        cursor.close()

    def _invoke(self, handler, path, payload, roles=None):
        with branding_gate.app.test_request_context(path, method="POST", json=payload):
            branding_gate.session["user_id"] = 1
            branding_gate.session["name"] = "Workflow Test User"
            branding_gate.session["username"] = "workflow-test"
            branding_gate.session["roles"] = roles or ["pricing"]
            endpoint = getattr(handler, "__wrapped__", handler)
            return endpoint(*self._handler_args(handler))

    def _handler_args(self, handler):
        if handler.__name__ in {
            "approve_sales_head_negotiation",
            "pricing_send_negotiation_to_costing",
            "pricing_decline_negotiation",
        }:
            return (self.negotiation_id,)
        if handler.__name__ == "set_item_prices":
            return (self.request_id,)
        return ()

    def _negotiation(self):
        cursor = self._cursor()
        cursor.execute(
            """
            SELECT status, destination_team, new_cost_price, new_selling_price
            FROM negotiation_requests WHERE id = %s
            """,
            (self.negotiation_id,),
        )
        result = cursor.fetchone()
        cursor.close()
        return result

    def _item(self):
        cursor = self._cursor()
        cursor.execute(
            """
            SELECT approval_status, negotiation_status, cost_per_item, sell_per_item
            FROM sales_request_items WHERE id = %s
            """,
            (self.item_id,),
        )
        result = cursor.fetchone()
        cursor.close()
        return result

    def test_sales_head_approval_always_routes_to_pricing(self):
        response = self._invoke(
            branding_gate.approve_sales_head_negotiation,
            f"/api/sales-head/negotiations/{self.negotiation_id}/approve",
            {"notes": "Approved", "destination": "costing"},
        )

        self.assertEqual(response.get_json()["success"], True)
        negotiation = self._negotiation()
        self.assertEqual(negotiation["status"], "pending_pricing")
        self.assertEqual(negotiation["destination_team"], "pricing")
        self.assertEqual(self._item()["negotiation_status"], "negotiated")

    def test_pricing_can_send_an_approved_negotiation_to_costing(self):
        self._set_negotiation_state("pending_pricing", "pricing")
        handler = getattr(branding_gate, "pricing_send_negotiation_to_costing")

        response = self._invoke(
            handler,
            f"/api/pricing/negotiations/{self.negotiation_id}/send-to-costing",
            {"notes": "Cost assumptions need review"},
        )

        self.assertEqual(response.get_json()["success"], True)
        negotiation = self._negotiation()
        self.assertEqual(negotiation["status"], "pending_costing")
        self.assertEqual(negotiation["destination_team"], "costing")
        self.assertEqual(self._item()["negotiation_status"], "pending_negotiation")

    def _client_as(self, role_code, user_id=9):
        client = branding_gate.app.test_client()
        with client.session_transaction() as current_session:
            current_session.update({
                "user_id": user_id,
                "mobile": "01050802925",
                "email": "%s@example.com" % role_code,
                "username": role_code,
                "name": role_code,
                "roles": [role_code],
                "perms": rbac.SEED_MATRIX[role_code],
                "role_code": role_code,
            })
        return client

    def test_pricing_manager_can_use_the_repricing_decision_api(self):
        self._set_negotiation_state("pending_pricing", "pricing")

        response = self._client_as("pricing_manager").post(
            f"/api/pricing/negotiations/{self.negotiation_id}/send-to-costing",
            json={"notes": "Pricing decision"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._negotiation()["status"], "pending_costing")

    def test_operations_can_no_longer_take_the_pricing_decision(self):
        """Pricing owns the re-pricing decision; Operations only re-costs."""
        self._set_negotiation_state("pending_pricing", "pricing")

        response = self._client_as("operations_manager").post(
            f"/api/pricing/negotiations/{self.negotiation_id}/send-to-costing",
            json={"notes": "Operations should not be allowed here"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._negotiation()["status"], "pending_pricing")

    def test_a_pricing_specialist_prepares_but_does_not_decide(self):
        self._set_negotiation_state("pending_pricing", "pricing")

        response = self._client_as("pricing_specialist").post(
            f"/api/pricing/negotiations/{self.negotiation_id}/decline",
            json={"reason": "Specialists may not decline"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._negotiation()["status"], "pending_pricing")

    def test_pricing_can_decline_and_return_the_existing_price_to_client_review(self):
        self._set_negotiation_state("pending_pricing", "pricing")
        handler = getattr(branding_gate, "pricing_decline_negotiation")

        response = self._invoke(
            handler,
            f"/api/pricing/negotiations/{self.negotiation_id}/decline",
            {"reason": "Requested price is below the viable selling price"},
        )

        self.assertEqual(response.get_json()["success"], True)
        self.assertEqual(self._negotiation()["status"], "pricing_declined")
        item = self._item()
        self.assertEqual(item["approval_status"], "pending")
        self.assertEqual(item["negotiation_status"], "none")
        self.assertEqual(float(item["sell_per_item"]), 160.0)

    def test_operation_recosting_returns_the_negotiation_to_pricing(self):
        self._set_negotiation_state("pending_costing", "costing")

        response = self._invoke(
            branding_gate.add_operation_request_costs,
            "/api/operations/requests/add-costs",
            {
                "request_id": self.request_id,
                "items": [{"id": self.item_id, "cost_per_item": 90}],
            },
        )

        self.assertEqual(response.get_json()["success"], True)
        negotiation = self._negotiation()
        self.assertEqual(negotiation["status"], "pending_pricing")
        self.assertEqual(negotiation["destination_team"], "pricing")
        self.assertEqual(float(negotiation["new_cost_price"]), 90.0)
        self.assertEqual(self._item()["negotiation_status"], "negotiated")

    def test_repricing_completes_the_active_negotiation(self):
        self._set_negotiation_state("pending_pricing", "pricing")
        cursor = self._cursor()
        cursor.execute(
            "UPDATE sales_request_items SET negotiation_status = 'negotiated' WHERE id = %s",
            (self.item_id,),
        )
        cursor.close()

        response = self._invoke(
            branding_gate.set_item_prices,
            f"/api/sales/requests/{self.request_id}/set-prices",
            {"items": [{"item_id": self.item_id, "sell_per_item": 145}]},
        )

        self.assertEqual(response.get_json()["success"], True)
        negotiation = self._negotiation()
        self.assertEqual(negotiation["status"], "pricing_completed")
        self.assertEqual(float(negotiation["new_selling_price"]), 145.0)
        item = self._item()
        self.assertEqual(item["approval_status"], "pending")
        self.assertEqual(item["negotiation_status"], "none")

    def test_sales_cannot_complete_a_negotiation_owned_by_pricing(self):
        self._set_negotiation_state("pending_pricing", "pricing")
        cursor = self._cursor()
        cursor.execute(
            "UPDATE sales_request_items SET negotiation_status = 'negotiated' WHERE id = %s",
            (self.item_id,),
        )
        cursor.close()

        response, status = self._invoke(
            branding_gate.set_item_prices,
            f"/api/sales/requests/{self.request_id}/set-prices",
            {"items": [{"item_id": self.item_id, "sell_per_item": 145}]},
            roles=["sales"],
        )

        self.assertEqual(status, 403)
        self.assertIn("Pricing role", response.get_json()["error"])
        self.assertEqual(self._negotiation()["status"], "pending_pricing")
        self.assertEqual(float(self._item()["sell_per_item"]), 160.0)


if __name__ == "__main__":
    unittest.main()
