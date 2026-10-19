# 05 - Supplier accounts and the Finance bar

**Goal:** Finance sees what it owes every supplier and what it paid, with a
statement per supplier, records supplier payments from a payment method, and
moves between Finance pages from one bar on each of them.

**Acceptance:**
- `tests/test_supplier_accounts.py`: opening + approved SR item cost − payment
  = owed, running balance and period folding, payment needs a method and
  enough balance, books an approved Supplier Payments expense, Excel exports,
  outsiders refused; the bar renders on every Finance page.
- Browser: George opens Finance > Suppliers, opens a supplier, records a
  payment; the balance drops and the payment appears in Finance Management.

**Status:** live 2026-10-19.
