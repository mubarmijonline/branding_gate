# 06 - Chart of accounts

**Goal:** the Finance Tree is Branding Gate's chart of accounts with codes; every
money movement posts to one account; system bookings land on their mapped
accounts; balances roll up by group and class.

**Acceptance:**
- `tests/test_finance_chart.py`: the chart is seeded with its codes and the
  system ids are on their accounts; group + account pickers post to the leaf;
  a group with accounts is refused; movements roll up on the normal side; live
  balances for 1101/1102/1103/2101/1110; next code and code validation;
  income statement counts posted invoices on 4101.
- Browser: George sees the six classes with codes, adds an account under 62,
  records an expense to it and sees it roll up to 62 and class 6.

**Status:** live 2026-10-22. Next: the year-end statements on top of it (07).
