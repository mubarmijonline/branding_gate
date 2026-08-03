# Pricing-Owned Negotiation Workflow

## Goal

Move the re-costing decision from Sales Head to Pricing while preserving the existing client negotiation, approval, costing, pricing, audit, and client-review journey.

## Approved Flow

1. Sales records the client's expected price and negotiation reason.
2. The negotiation enters `pending_sales_head`.
3. Sales Head may decline it or approve it.
4. Sales Head approval always sends it to Pricing as `pending_pricing`.
5. Pricing owns three actions:
   - Re-price directly by entering a new selling price.
   - Send to Operations for re-costing first.
   - Decline and return the item to pending client approval with its existing price.
6. Re-costing changes the cost and returns the negotiation to Pricing.
7. Re-pricing changes the selling price and returns the item to pending client approval.

## State Contract

| Current state | Actor | Action | Next state | Item state |
|---|---|---|---|---|
| `pending_sales_head` | Sales Head | approve | `pending_pricing` | `pending_negotiation` / `negotiated` |
| `pending_sales_head` | Sales Head | decline | `sales_head_declined` | `pending` / `none` |
| `pending_pricing` | Pricing | re-price | `pricing_completed` | `pending` / `none` |
| `pending_pricing` | Pricing | send to re-costing | `pending_costing` | `pending_negotiation` / `pending_negotiation` |
| `pending_pricing` | Pricing | decline | `pricing_declined` | `pending` / `none` |
| `pending_costing` | Operations | complete re-costing | `pending_pricing` | `pending_negotiation` / `negotiated` |

Existing rows already in legacy states remain readable. New transitions must reject stale or duplicate actions instead of silently processing them twice.

## Permissions

- Sales: create negotiations and view the resulting client-approval state.
- Sales Head: approve to Pricing or decline; no Costing/Pricing destination choice.
- Pricing: view pricing work, send an approved negotiation to re-costing, decline it, or enter the new selling price. The current project maps this responsibility to the existing `operation` role while also accepting a future `pricing` role.
- Operations: enter cost changes only for work routed to re-costing, then return it to Pricing.
- Admin: retains the existing global role bypass.

## Interface Changes

- Sales Head approval modal explains that approval always sends the negotiation to Re-Pricing.
- Pricing identifies negotiations awaiting its decision and displays client expected price, current cost, and current selling price.
- Pricing presents explicit `Re-Price`, `Re-Cost First`, and `Decline` controls.
- A Pricing decline requires a reason.
- Re-costed negotiations display that the updated cost is ready for Pricing review.

## Audit And Compatibility

- Every transition writes a `negotiation_logs` entry and a main item change-log entry.
- `destination_team` remains for compatibility and records the current destination.
- The database status enum gains `pricing_declined`.
- Saving a negotiated selling price marks the corresponding active negotiation `pricing_completed` and records `new_selling_price`.
- Completing negotiation re-costing records `new_cost_price`, changes the negotiation back to `pending_pricing`, and records `destination_team='pricing'`.

## Validation

- Automated policy tests cover all valid transitions and reject invalid actor/action/state combinations.
- Route regression tests or focused source-level integration checks cover role gates and state updates where full database isolation is impractical.
- Existing project tests remain green.
- The generated Sales Request flowchart PDF shows Pricing as the owner of the re-costing decision.
- After restart, authenticated route checks and service logs verify the deployed application is healthy.
