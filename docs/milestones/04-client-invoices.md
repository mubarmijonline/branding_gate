# 04 - Client invoices and statements

**Goal:** account managers draft invoices from a Sales Request, Finance posts
them, and every client and company has a statement of account.

**Acceptance:**
- `tests/test_invoicing.py`: the sample's arithmetic (2452 → 178,088), the
  draft → submitted → posted flow and who may do each step, numbers unique,
  posted invoices locked, statement running balance with opening balance.
- Browser: an account manager drafts from an SR and submits; George posts;
  the print view matches the sample; the client's statement shows it.

**Status:** live 2026-10-19. Item list waits for George's Excel (Finance imports it on the Invoice Items tab). User guide: docs/guides/client-invoices.md.
