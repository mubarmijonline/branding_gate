# Pricing-Owned Negotiation Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Sales Head approval route every negotiation to Pricing, then let Pricing re-price, request re-costing, or decline.

**Architecture:** Add a small pure-Python workflow policy as the canonical state/action contract and use it from the existing Flask endpoints. Keep database writes in the current transaction boundaries, extend the existing enum compatibly, and update the two existing dashboards rather than creating a parallel workflow UI.

**Tech Stack:** Python 3.12, Flask, MySQL, Jinja2, jQuery/Bootstrap, pytest, ReportLab

## Global Constraints

- Sales Head never selects Costing versus Pricing after approval.
- Pricing owns the direct re-price, re-cost-first, and decline choices.
- Operations re-costing returns the negotiation to Pricing.
- Every workflow mutation is role-gated, state-validated, logged, and transactional.
- Existing negotiation data remains readable.
- Restart `branding_gate.service` and verify the live application after implementation.

---

### Task 1: Workflow Policy And Schema

**Files:**
- Create: `negotiation_workflow.py`
- Create: `tests/test_negotiation_workflow.py`
- Create: `negotiation_pricing_owner_migration.sql`

**Interfaces:**
- Produces: `transition(current_state: str, actor: str, action: str) -> str`
- Produces: `InvalidNegotiationTransition(ValueError)`

- [ ] **Step 1: Write failing tests for the approved transition matrix and invalid transitions.**
- [ ] **Step 2: Run `pytest -q tests/test_negotiation_workflow.py` and confirm the failure is caused by the missing policy module.**
- [ ] **Step 3: Implement the minimum constants, exception, and `transition()` function needed by the tests.**
- [ ] **Step 4: Re-run the focused tests and confirm they pass.**
- [ ] **Step 5: Add an idempotent migration that extends `negotiation_requests.status` with `pricing_declined`, preserving every existing enum value.**
- [ ] **Step 6: Apply the migration and verify the resulting table definition.**

### Task 2: Backend State Transitions

**Files:**
- Modify: `branding_gate.py:6561`
- Modify: `branding_gate.py:8188`
- Modify: `branding_gate.py:12530`
- Modify: `branding_gate.py:12599`
- Create: `tests/test_negotiation_route_contract.py`

**Interfaces:**
- Consumes: `transition()` from Task 1.
- Produces: `POST /api/pricing/negotiations/<id>/send-to-costing`.
- Produces: `POST /api/pricing/negotiations/<id>/decline`.

- [ ] **Step 1: Write failing route-contract tests asserting Sales Head approval ignores destination choice, Pricing routes are role-gated, re-costing returns to Pricing, and re-pricing completes the active negotiation.**
- [ ] **Step 2: Run the focused route-contract tests and confirm each assertion fails against the current source.**
- [ ] **Step 3: Change Sales Head approval to transition only from `pending_sales_head` to `pending_pricing`, set `destination_team='pricing'`, and mark the item ready for Pricing review.**
- [ ] **Step 4: Add Pricing send-to-costing and decline endpoints with required-state validation, audit logs, item updates, and Pricing/Admin authorization.**
- [ ] **Step 5: Gate cost mutation with Operations authorization and update active `pending_costing` negotiations to `pending_pricing` after their item is re-costed.**
- [ ] **Step 6: Permit Pricing to load request/item data and save selling prices; when a negotiated item is saved, complete its active `pending_pricing` negotiation and record the new price.**
- [ ] **Step 7: Run route-contract and policy tests until green.**

### Task 3: Sales Head And Pricing Interfaces

**Files:**
- Modify: `templates/sales_head_approval.html:295`
- Modify: `templates/sales_request.html:3262`
- Test: `tests/test_negotiation_route_contract.py`

**Interfaces:**
- Consumes: Pricing endpoints from Task 2.
- Produces: Sales Head fixed-destination approval UI and Pricing decision controls.

- [ ] **Step 1: Add failing template contract tests for fixed Re-Pricing routing and all three Pricing actions.**
- [ ] **Step 2: Run the focused tests and verify the expected missing controls cause failure.**
- [ ] **Step 3: Remove Sales Head destination cards and submit only notes to the approval endpoint.**
- [ ] **Step 4: Update Sales Head status labels to distinguish Pricing review, re-costing, Pricing decline, and completed re-pricing.**
- [ ] **Step 5: In the pricing modal, show the negotiation decision controls only for `pending_pricing` items and display accurate re-costing context.**
- [ ] **Step 6: Wire `Re-Cost First` and `Decline` to the new APIs, require a decline reason, and keep direct price save as the actual Re-Pricing action.**
- [ ] **Step 7: Run focused frontend contract tests.**

### Task 4: Flowchart And End-To-End Verification

**Files:**
- Modify: `docs/sales-request-journey.md`
- Modify: `docs/generate-sales-request-journey-pdf.py`
- Modify: `tests/test_sales_request_journey_pdf.py`
- Regenerate: `docs/sales-request-journey-and-privileges.pdf`
- Regenerate: `docs/sales-request-journey-flow.png`

**Interfaces:**
- Consumes: Approved workflow wording and state ownership.
- Produces: Updated client-facing flowchart PDF and preview.

- [ ] **Step 1: Update the PDF test to require Sales Head-to-Re-Pricing and the Pricing decision branch.**
- [ ] **Step 2: Run the PDF test and confirm it fails against the old chart.**
- [ ] **Step 3: Update the Markdown and ReportLab generator with the new flow and role controls.**
- [ ] **Step 4: Regenerate the PDF/PNG and run PDF tests.**
- [ ] **Step 5: Run `python -m py_compile branding_gate.py negotiation_workflow.py` and the complete `pytest -q` suite.**
- [ ] **Step 6: Restart `branding_gate.service`, inspect service logs, and verify the local and HTTPS application endpoints respond.**
- [ ] **Step 7: Inspect the regenerated PNG for clear arrows, readable labels, and no overlap.**

## Self-Review

- Spec coverage: all actors, actions, database states, UI controls, audit requirements, PDF updates, restart, and validation are assigned to tasks.
- Placeholder scan: no deferred implementation placeholders are present.
- Type consistency: Tasks 2 and 3 consume the exact `transition(current_state, actor, action)` policy and named endpoints defined by Tasks 1 and 2.
- Compatibility: the plan extends the enum and reuses `destination_team` rather than deleting legacy fields or rewriting old records.
