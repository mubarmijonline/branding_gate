import unittest

from negotiation_workflow import InvalidNegotiationTransition, transition


class NegotiationWorkflowTest(unittest.TestCase):
    def test_transition_allows_the_approved_negotiation_flow(self):
        transitions = [
        ("pending_sales_head", "sales_head", "approve", "pending_pricing"),
        ("pending_sales_head", "sales_head", "decline", "sales_head_declined"),
        ("pending_pricing", "pricing", "reprice", "pricing_completed"),
        ("pending_pricing", "pricing", "send_to_costing", "pending_costing"),
        ("pending_pricing", "pricing", "decline", "pricing_declined"),
        ("pending_costing", "operation", "complete_costing", "pending_pricing"),
        ]
        for current_state, actor, action, expected_state in transitions:
            with self.subTest(current_state=current_state, actor=actor, action=action):
                self.assertEqual(
                    transition(current_state, actor, action), expected_state
                )

    def test_transition_rejects_wrong_owner_or_stale_action(self):
        invalid_transitions = [
        ("pending_sales_head", "sales_head", "send_to_costing"),
        ("pending_pricing", "sales_head", "send_to_costing"),
        ("pending_costing", "pricing", "reprice"),
        ("pricing_completed", "pricing", "reprice"),
        ("pricing_declined", "pricing", "send_to_costing"),
        ]
        for current_state, actor, action in invalid_transitions:
            with self.subTest(current_state=current_state, actor=actor, action=action):
                with self.assertRaises(InvalidNegotiationTransition):
                    transition(current_state, actor, action)

    def test_transition_error_identifies_the_rejected_transition(self):
        with self.assertRaises(InvalidNegotiationTransition) as context:
            transition("pending_sales_head", "sales_head", "send_to_costing")

        message = str(context.exception)
        self.assertIn("pending_sales_head", message)
        self.assertIn("sales_head", message)
        self.assertIn("send_to_costing", message)


if __name__ == "__main__":
    unittest.main()
