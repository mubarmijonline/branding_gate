# 12 - Paying supplier purchases by request

**Goal:** Finance pays what a request owes each supplier from a payment method
chosen on that request; the payment posts Dr 2101 / Cr the method's code
(1101 cash row, 1102 bank row).

**Acceptance:**
- `tests/test_supplier_purchases_by_request.py`: purchased / paid / remaining
  per (SR, supplier); paying from cash posts on 1101 and from a bank on 1102
  against 2101; paying more than remaining on the SR is refused; outsiders
  refused.
- Browser: George opens Finance > Suppliers, sees SR purchases to pay, pays one
  from a bank; it leaves the list's remaining and shows on the bank's ledger.

**Status:** live 2026-11-03. Open with George: posting the purchase itself (5101 or 1105 / 2101), purchase VAT (1106), advances (1108).
