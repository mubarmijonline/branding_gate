# 09 - Quick approval from a notification

**Goal:** whoever an approval waits on can open it from the notification, see
the details, approve or decline through the same flow as the approval page,
and the notification then reads Approved / Declined. The Approvals menu shows
a count on each item, so its number says which page it is on.

**Acceptance:**
- `tests/test_quick_approvals.py`: states follow the stage; a leader sees an
  عهدة waiting, approves it through the manager endpoint the modal returns,
  and it then reads approved; decline needs a reason; someone off the line is
  refused by the same rule; people without the permission cannot read it.
- Browser: Haitham's tray shows "Show details" on REQ-89368, the modal lists
  the request and approves it, the row turns to Approved; George's finance
  stage shows details with "Open the approval page"; the Approvals menu shows
  the count beside Expense Approvals.

**Status:** live 2026-10-27.
