# 13. Target month columns and per-person reports

**Goal.** Gamal (2026-11-08): see every month, open any person to see where
their target came from and every request behind their number, as a detailed
report, on a clearer page, for every department.

**Acceptance check.**
- `/targets` shows one column per month (achieved of month target, bar,
  current month marked); names and Achieved open the report.
- `/targets/person/<id>?period=` shows headline, KPIs, months, target path,
  team, requests with filters, clients, year; prints cleanly; EN and AR.
- The report's approved total equals the table's Achieved; out-of-scope
  people are refused (`tests/test_targets_person.py`).

**Status.** Live 2026-11-08.
