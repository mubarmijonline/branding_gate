import unittest

from flask import render_template

import branding_gate
import rbac


class NegotiationTemplateTest(unittest.TestCase):
    def _render(self, template_name, **context):
        with branding_gate.app.test_request_context("/"):
            branding_gate.session["user_id"] = 1
            branding_gate.session["role_code"] = "admin"
            branding_gate.session["roles"] = ["admin"]
            # Templates gate on the permission set, not on role names.
            branding_gate.session["perms"] = rbac.SEED_MATRIX["admin"]
            return render_template(template_name, **context)

    def test_sales_head_approval_has_a_fixed_repricing_destination(self):
        html = self._render("sales_head_approval.html")

        self.assertIn("Approval sends this negotiation to Re-Pricing", html)
        self.assertNotIn('id="approveDestination"', html)
        self.assertNotIn('class="card h-100 destination-card"', html)
        self.assertIn("Approve &amp; Send to Re-Pricing", html)

    def test_pricing_modal_exposes_all_pricing_owned_decisions(self):
        html = self._render("sales_request.html", pricing_mode=True)

        self.assertIn("pricing-reprice-now", html)
        self.assertIn("pricing-send-to-costing", html)
        self.assertIn("pricing-decline-negotiation", html)
        self.assertIn("/send-to-costing", html)
        self.assertIn("/decline", html)

    def test_sales_request_modal_exposes_pricing_decisions_outside_pricing_mode(self):
        html = self._render("sales_request.html", pricing_mode=False)

        self.assertIn(
            "if (window.CAN_CONTROL_PRICING && isPricingDecision && activeNegotiation)",
            html,
        )
        self.assertNotIn(
            "if (window.PRICING_MODE && window.CAN_CONTROL_PRICING && isPricingDecision",
            html,
        )

    def test_pricing_input_dialogs_mount_inside_the_parent_modal(self):
        html = self._render("sales_request.html", pricing_mode=False)

        self.assertGreaterEqual(
            html.count("target: document.getElementById('setPriceModal')"),
            2,
        )


if __name__ == "__main__":
    unittest.main()
