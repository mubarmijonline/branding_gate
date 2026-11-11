# 14. Supplier accounts under 2101 and staff expenses paid to suppliers

**Goal.** Ahmed (2026-11-11): an expense from custody must name a supplier
Finance knows and carry its document; Finance sees the document and what the
SR owes that supplier; approving posts to 2101; every supplier is its own
account under 2101 (21011, 21012, ...) with a full report.

**Acceptance check.**
- A typed supplier is refused; the company is the name shown; the supplier
  list has no "Unknown".
- On a request, only that request's suppliers are offered and accepted.
- No document: not sent (`/api/my-expenses/submit`), not approved
  (`finance-approve-bulk`), last file of a sent expense not removable.
- A supplier line is approved with no category and posts to 2101 with its
  supplier and SR; Finance's list shows owed/paid/remaining for that SR.
- Finance Tree: suppliers under 2101 with their codes, owed from approved items
  (Dr 5101 / Cr supplier) and paid; the tree stays balanced; a supplier opens
  its report (`tests/test_supplier_expense_accounts.py`).

**Status.** Live 2026-11-11.
