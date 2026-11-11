# 17. Supplier assignment approved by Finance, agreed vs actual cost

**Goal.** Ahmed (2026-11-11): assigning a supplier waits for Finance (it is what
puts the cost into the tree), with documents; only the Operations head and team
leaders assign; an actual cost above the agreed cost needs David first; every
Finance approval can be decided from its notification with all data and files.

**Acceptance check.**
- A supplier change on an item is refused without a request; a request needs a
  document; the item changes only when Finance approves, with the actual cost
  owed.
- Above agreed: head first (Supplier Cost Approvals), then Finance; the head's
  own request goes straight to Finance.
- An operations member cannot assign.
- Finance decides an assignment, a My Expenses line (payment method, account,
  receipt) from the notification (`tests/test_supplier_assignment_approval.py`).

**Status.** Live 2026-11-11.
