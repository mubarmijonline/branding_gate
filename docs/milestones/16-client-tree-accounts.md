# 16. Client accounts under 1103

**Goal.** Ahmed (2026-11-11): clients coded and numbered under 1103 like
suppliers under 2101 (11031, 11032, ...), each opening a full report.

**Acceptance check.**
- Every client is a row under 1103 with its code; 1103 is their sum; the tree
  balances; each client's balance equals their statement.
- A new client takes the next code.
- A staff expense's custody leg naming a client is not a collection
  (`tests/test_client_tree_accounts.py`).

**Status.** Live 2026-11-11.
