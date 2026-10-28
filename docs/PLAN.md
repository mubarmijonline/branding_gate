# Plan — عهدة, on its way up and back down

Everything here is **عهدة**: money the company hands to a person, which that
person spends against real work and eventually accounts for. One idea runs
through it — **money moves one layer at a time, and the layer above you signs
before Finance ever sees it.**

Status: **signed off. Building.**

## The shape of it

**One running عهدة per person.** Not a numbered advance each time: a single
custody balance that approved requests add to and approved expenses draw down.
That is the balance already in `user_finance_balances`, so nothing recorded so
far is lost or re-entered.

```
        request  ──► manager ──► Finance ──►  ┌──────────────┐
                                              │   عهدة       │
        expense  ◄── manager ◄── Finance ◄──  │  (a running  │
        (against a sales request)             │   balance)   │
                                              └──────┬───────┘
                                    return leftover  │
                                    recorded by Finance
                                    back onto a payment method
```

### Decided

1. **A sales request per expense line**, not per sheet.
2. **The manager may edit any money value** — the expense amounts and the
   requested عهدة amount alike. The original is kept either way.
3. **No re-confirmation by the submitter.** A manager's edit goes straight on to
   Finance, as asked.
4. **The CEO's own request** goes straight to Finance.
5. **Leftover عهدة is returned and recorded.**
6. **تسوية عهدة is raised by the person holding it**, not by Finance. Whenever
   someone has a remaining balance they get a *Settle عهدة* action showing what
   they were given, what they have spent against sales requests, and what is
   left. They declare the amount they are handing back; Finance confirms it has
   arrived, chooses the payment method it goes onto, and only then does the
   عهدة fall. A settlement is one more row on `user_balance_transfers` with
   `transfer_type = 'settlement'`, so it queues, notifies and reads exactly like
   a request, in the other direction. No manager step: handing money back is not
   spending it. *(Say so if you want the manager on this one too.)*

---

## 1. Balance request

### The flow you asked for

```
someone asks for balance
      │
      ├─ the line above approves         ← any of them, never the CEO
      │
      ├─ Finance approves (picks the payment method)
      │
      └─ the money lands on their balance
```

### Who skips the manager step

Nine people report directly to the CEO and are therefore their own top layer:

Sales Head · Assistant · Marketing Manager · Finance Manager · Account Director ·
2D Designer Head · 3D Head · Operations Manager · Pricing Manager

Their requests are created already waiting on Finance. Everyone else — team
leaders and members — waits on their own manager first. The rule is read from
`user.manager_id`, not from a list of names, so it survives a transfer or a new
hire with no edit here.

### What changes

**`user_balance_transfers`**

| Column | Why |
|---|---|
| `status` gains `pending_manager`, `pending_finance` | Two queues need two words. `pending` cannot say who is holding it |
| `manager_approved_by`, `manager_approved_at`, `manager_notes` | Same three columns, same names, as `expense_tracking` already uses |

Existing rows: both are `approved`, so the migration maps nothing and nothing
moves. There are no live pending requests to strand.

**Permissions**

- `user_balance.approve_manager` — new. Granted at `team` scope to every role
  that has people under it (heads and team leaders).
- `user_balance.approve` — unchanged, and now means *the Finance step*.

**Who may approve whom.** Holding the permission is not enough: the route checks
that you are somewhere in the line *above* the requester — their manager, their
manager's manager, and so on up to but never including the CEO. Any one of them
can act and all of them are told, so a leader on leave cannot hold up their
member's عهدة while the head is right there. Same rule as targets — reading
follows scope, writing is narrower and is checked in the route.

**Routes**

- `POST /api/finance/balance-requests/<id>/manager-approve` — new
- `POST /api/finance/balance-requests/<id>/manager-reject` — new, reason required
- the existing approve/reject become the Finance step and refuse anything not
  already `pending_finance`

**Queues.** The approvals page gains a "Waiting on me" list for managers. The
existing Balance Requests tab keeps showing Finance its own queue.

---

## 2. Recording an expense

### The flow you asked for

```
someone records an expense, against a sales request that exists
      │
      ├─ their manager approves        ← and may correct any of the amounts first
      │
      ├─ Finance approves
      │
      └─ posted as it is today: one income line in, one expense line out
         per item, against that item's category
```

### What changes

**Every expense line names a sales request.** `expense_tracking_items` gains
`sales_request_id`, required, validated against `sales_request` on the way in —
not free text, not a number nobody checks. Per line rather than per sheet, so one
submission can cover work on two requests. *(Confirm: per line, or one for the
whole sheet?)*

`/my-expenses` already requires a sales request; this brings the reimbursement
sheet in line with it.

**The manager approves, and may edit first.** Today `manager-approve` accepts
anyone holding the permission, for anybody's sheet — it never looks at the
reporting line. It will check it, exactly like the balance step.

Editing amounts is `expense_tracking.edit_amount`, today Finance-only. The
manager gets it at `team` scope while the sheet is still `pending`. The original
figure is already kept in `original_total_amount` / `original_amount`, so what
was claimed and what was approved both stay on the record and the submitter can
see the difference.

**Finance is unchanged.** Once the manager sends it on, everything Finance does
today happens exactly as it does now — the income transaction, the per-item
expense transactions, the category posting, the balance deduction.

**Notifications** at every hop, to the person who has to act next and to the
submitter when the answer comes back. Nothing in either flow is silent.

---

## What I am not deciding for you

1. **SR per line or per sheet?** Plan assumes per line.
2. **May a manager change the *balance* amount** the way they can change an
   expense amount? Plan assumes no — a balance request is approved or refused as
   asked.
3. **After a manager edits an amount, does the submitter re-confirm?** Plan
   assumes no: it goes straight to Finance, as you described.
4. **The CEO's own balance request** — plan assumes it goes straight to Finance.

---

## Order of work

1. Migration: the new columns and statuses. DDL outside any transaction, since
   `ALTER TABLE` commits implicitly in MySQL.
2. `rbac.py`: the new permission and its grants; re-seed.
3. Balance: manager step, the two routes, the skip rule, the queues.
4. Expense: the SR link and its validation, the reporting-line check, the
   manager's edit window.
5. Tests: the skip rule, the reporting-line refusals, an SR that does not exist,
   the money posted at the end.
6. Deploy, then verify each flow in the browser as a member, a manager and
   Finance.

---

# Client Accounts (Finance), 2026-10-16

**Ask:** one Finance page with every client and parent company, each with a
profile showing its requests, items and transactions in depth; every
transaction from an SR tied to that SR's client; a full report.

**Found:** FIN202610-59779, an approved EGP 20,000 Client Payment, was saved
with no client and no SR. Nothing required either on a Client Payment.

**Rule (server-side, `link_transaction_to_request`):**
- A transaction naming an SR takes its client from the SR; naming a different
  client alongside is refused.
- A Client Payment (category 1) must name its SR.
- Old unlinked Client Payments are listed and can be linked once
  (`POST /api/finance/transactions/<id>/link-request`, logged as `modified`).

**Figures (one loader, `client_accounts_data`, feeds page, profiles, workbook):**
quoted = all item sell; approved = items the client approved; collected =
approved income; pending = income awaiting approval; outstanding = approved
minus collected; margin = approved sell minus approved cost; paid out =
approved expenses on the party's requests. Requests dated by created_at,
transactions by transaction_date.

**Screens:** `/finance/accounts` (companies, expandable to clients),
`/finance/accounts/company/<id>`, `/finance/accounts/client/<id>`
(profile, figures, requests expandable to items, transactions, clients).
Full Report: `/api/finance/accounts/report` (Companies, Clients, Requests,
Items, Transactions, Unlinked Payments), for all or one party, in a date range.
Access: `finance_report.view`; linking: `finance_txn.approve`.

---

# Arabic interface, 2026-10-16

**Ask:** Arabic across the whole system, an easy EN/AR toggle, English by default.

**Approach:** a dictionary applied in the page, not gettext. 45 templates and
~64k lines of markup, plus text that JavaScript builds at runtime (tables,
popups, notifications), would take weeks to mark up by hand and would still
miss the runtime text. Instead:
- The choice lives in a `bg_lang` cookie (`/lang/ar`, `/lang/en`, one year),
  default `en`. `<html lang dir>` follow it on every page, login included.
- Arabic only: `static/css/bg-rtl.css` (RTL flips for Bootstrap 4 utilities,
  dropdowns, modals, inputs, tables, select2, icons; Cairo font),
  `static/i18n/ar.js` (English -> Arabic, ~3.6k entries, `{0}` holes for
  numbers and names) and `static/js/bg-i18n.js` (translates text, placeholders,
  tooltips, button labels and native dialogs as they reach the page, through a
  MutationObserver). English loads none of it.
- Data stays as entered: names, items, codes and amounts are not translated.
  Whatever fills a `{0}` hole is shown as stored; the server sends the
  dictionary words that are also stored values (`i18n_protected_words`, the
  overlap only, cached 10 min), and those are never translated; text already
  written "English | عربي" is left as written. `data-no-i18n` opts an element out.
- Not translated: Excel/PDF exports and stored notification text that has no
  pattern in the dictionary.

**Maintenance:** `python3 scripts_i18n_missing.py` lists strings the pages use
that the dictionary lacks; translate them and add them to `static/i18n/ar.js`.

---

# Receipts on My Expenses, 2026-10-18

**Ask:** optional photos or documents when adding an expense, shown clearly on
the Sales Request it was spent on.

- `expense_attachments` (`expense_attachments_migration.sql`), files under
  `private_uploads/expenses/<expense_id>/`, outside the nginx-served `uploads/`.
- Upload/remove by the expense's owner until Finance decides (draft, submitted,
  manager_approved); photos, PDF, Word, Excel; 10MB each, 10 per expense.
- Read through `/api/expense-attachments/<id>`: the owner, an approver whose
  `expense_tracking.view` scope reaches the owner, or anyone who may open the
  linked request.
- Shown in My Expenses (Files column), the approval screens (paperclip), and an
  "Expenses & Receipts" section on the Sales Request page (sent expenses only,
  approved and awaiting totals). Shared viewer: `static/js/bg-expense-files.js`.

---

# Uploaded files behind the login, 2026-10-18

nginx served `uploads/` from disk to anyone holding a link (item attachments,
costing alternatives and proposals, company documents, request files). The
public `location /uploads/` is gone from `branding_gate_nginx.conf`; requests
reach `serve_upload` (`/uploads/<path>`), which wants a session and:
- `items/`, `alternatives/`, `costing/`, `sales_requests/`: an item desk
  permission (costing, pricing, approved items, client approval, negotiation,
  supplier report), or `sales_request.view` whose scope reaches the request owner;
- `companies/`: `company.view` or `client.view`;
- anything else: refused. Paths outside `uploads/` are 404.
Responses are `Cache-Control: private`. Stored URLs are unchanged.

---

# Client invoices and statements of account, 2026-10-19

**Ask (George, Finance head):** the client side of the books. Invoices built
from the company's item list, issued by the client's account people, posted
to the client's account, and a statement of account per client.

**Decided with Ahmed:**
- The account manager drafts the invoice and sends it to Finance; George
  posts it. Only a posted invoice counts on the client's account.
- Lines come from the Sales Request's client-approved items (with their
  prices), each given an item code from George's list; lines can be edited,
  removed or added.
- VAT 14% is always added; the 1% commercial-profits tax (أ.ت.ص) is deducted
  per invoice, ticked by default.
- The item list (104 codes, Arabic and English names) comes from George's
  Excel; Finance imports it on the Invoice Items page and maintains it there.

**Arithmetic (matches the sample, invoice 2452):** per line, sales value =
qty × price − cash discount; VAT = 14% of sales value. Invoice: subtotal =
Σ sales value; VAT = Σ line VAT; profit tax = 1% of subtotal when ticked;
total = subtotal + VAT − profit tax (157,600 + 22,064 − 1,576 = 178,088).
Money in Decimal, rounded to 2 places per line. Pure logic in `invoicing.py`.

**Data:** `invoice_catalog` (code, name_ar, name_en, active); `client_invoice`
(number assigned on posting, unique; SR, company, client, invoice date,
billing month, rates, totals, status draft → submitted → posted, or returned
with a reason); `client_invoice_line`. Company code = company id; registration
number = the company's tax number.

**Permissions:** `invoice.view` (scoped like sales requests on the
sales/account ladder; all for Finance), `invoice.create` (own; sales/account),
`invoice.post` (Finance manager), `invoice_catalog.edit` (Finance manager).

**Screens:** Finance > Invoices (list by stage, new invoice from an SR,
review and post or return), printable invoice in the sample's layout, Invoice
Items (catalog with Excel import), and a Statement tab on each client /
company profile in Client Accounts (posted invoices debit, approved payments
credit, running balance, date range with opening balance, Excel export).
Client Accounts gains Invoiced and Balance due.

**Revised 2026-10-19 (George's statement sample, Ahmed's notes):** lines are
only the SR's client-approved items (server-enforced, name from the SR, no
typed lines); an invoice takes its serial when drafted, from
`invoice_series.next_number` (set once by Finance to continue the paper
series) or the highest used + 1; a cancelled draft releases its number. The
statement follows George's sheet (Date, Job code, Invoice no., Description,
Debit, Credit, Balance; cash collections to the safe, cheque / bank to the
bank by payment-method type) and opens with balances brought forward
(`client_opening_balance`, set by Finance). Combined balances by company or
client: `/api/finance/accounts/balances`. Pages are full width. In Arabic the
minus sign follows the amount (bg-i18n `minusAfter`).

**Refunds and money on posting, 2026-10-19:** a refund is a `client_invoice` of
kind `refund` against a posted invoice (`refund_of`), lines chosen from it with
each ticked line refunded in full (what is left of it; revised 2026-10-19, no
partial quantities) (`refund_of_line`), at its prices and taxes; own
series R-n (`invoice_series` id 2). Posting either kind requires a payment
method and an amount (default the total, 0 = owed): `book_client_money` books
an approved Client Payment (income) or Client Refunds (expense) transaction,
moving the payment method balance with history, so it reaches Finance's
balances and reports. Statement: refund = credit, refund paid back = debit;
Client Accounts' Invoiced is net of refunds. Finance > Clients groups Client
Accounts & Statements, Invoices & Refunds and Combined Balances.

# Supplier accounts and one Finance bar, 2026-10-19

**Ask:** the same as Clients, for suppliers: what we owe each one, what we paid,
a statement and combined balances; and the Finance page links on every Finance
page.

**Ledger (`supplier_ledger_entries`):** credit (we owe) = balance brought
forward (`supplier_opening_balance`, set by Finance; negative = advance) + the
cost (`total_cost`) of SR items with that supplier once the client approved
them; debit (we paid) = approved expense transactions carrying `supplier_id`
(Finance's own and staff expenses Finance approved). Balance = credit − debit.
Credit stock held from the supplier is listed on the statement as goods only.

**Screens:** Finance > Suppliers > Supplier Accounts & Statements
(`/finance/suppliers`, all suppliers with opening, purchases, paid, owed,
period filter, Excel مجمع حسابات الموردين) and one statement per supplier
(`/finance/suppliers/<id>`, Excel كشف حساب مورد). Record payment (perm
`finance_txn.approve`) books an approved Supplier Payments expense from a
payment method via `book_client_money(..., supplier_id=)`, so it shows in
Finance Management. API under `/api/finance/supplier-accounts`.

**Finance bar:** `_finance_nav.html`, included by `main.html` on every Finance
endpoint (Overview, Management, Approvals; Clients; Suppliers; Expenses), each
link behind its own permission. Replaces `_clients_nav.html`.

# Chart of accounts replaces the Finance Tree, 2026-10-22

**Ask:** replace the income/expense category tree with Branding Gate's chart of
accounts (دليل الحسابات), with its codes. Decided with Ahmed: the chart sits over
the existing cash entries (no double entry); the system's own bookings map to:
client payment → 1103 العملاء, supplier payment → 2101 الموردين, custody,
staff loan and loan repayment → 1110 سلف وعهد للموظفين, opening balance → 3101
راس المال, client refund → 4102 مردودات ومسموحات المبيعات, other income → 4201.

**Chart:** `finance_chart.py` holds the sheet (classes 1-6, groups, accounts),
with two fixes: قروض بنكية is 2201 (the sheet repeated 2101), and spelling
(البيعية، الأثاث، المستحقة). `finance_categories` gains `account_code`
(unique) and `category_type` gains asset / liability / equity (class 1 asset,
2 liability, 3 equity, 4 income, 5-6 expense). The system rows keep their ids
(1, 2, 3, 4, 10, 11, 16, 44, 46) and become their accounts, so every booking in
the code is unchanged; custody and loans become four sub-accounts of 1110
(111001 صرف عهدة = 16, 111002 تسوية عهدة = 44, 111003 سلف = 11, 111004 سداد سلف
= 3). The old non-system categories are removed (no transactions use them
after the 2026-10-22 reset).

**Posting:** a transaction posts to one leaf account: `category_id` = the
account, `subcategory_id` NULL. Pickers keep their two-level shape (group, then
account); `posting_account()` turns any (category, sub-category) pair into the
leaf and refuses a group that has accounts under it. Applied wherever a
category comes from a request (add transaction, staff expense approval single
and bulk, expense-tracking approval). The single staff-expense approval no
longer defaults to the deleted Operational Expenses; a category is required.

**Values in the tree (revised 2026-10-22, Ahmed):** only approved finance transactions, each under the account it was posted to: money in and money out per account, rolled up to group and class. No figures derived from SRs, invoices or live balances (those were showing supplier SR costs on 2101 before anything was paid). The income statement still counts posted invoices on 4101 and refunds on 4102. Every payment method is a row under 1101 (cash) or 1102 (bank), built from payment_methods each time, with the approved money through it and its current balance; + on 1101 / 1102 adds a payment method of that kind.

**Reports:** the income statement and analytics roll up by group over classes
4 (revenue) and 5-6 (costs and expenses). 4101 Sales also counts posted
invoices (subtotal) and 4102 posted refunds (minus), since client payments now
go to 1103, not to revenue. The balance sheet is unchanged.

**Editing:** add an account or sub-account under any node (code suggested as
the next free one under the parent, editable, unique, must start with the
parent's code), rename, re-code and delete non-system ones. Classes and the
mapped system accounts cannot be renamed or deleted. The Categories tab shows
the same chart.

**Transfers between payment methods (2026-10-22):** in Add Income / Add Expense
the Account list also offers the other payment methods (Finance approvers only).
Saving books an approved transfer (`/api/finance/payment-methods/transfer`): out
of the source method posted to the target's account (1101 / 1102), into the
target posted to the source's. The tree shows it on both methods' rows; the
income and expense totals leave postings to 1101 / 1102 out.

**Opening balances are capital (2026-10-22):** a payment method's opening amount
and any later balance adjustment are booked as an approved transaction on 3101
راس المال (`book_capital`: in when the balance rises, out when it falls), not a
bare balance change. The balance sheet's equity shows Capital (class 3 net) and
its earnings, like the income/expense cards, leave capital and transfers out, so
cash on one side equals capital on the other. Ahmed's 100,000 opening on
Branding Gate CIB (history row 264, no transaction) was re-booked this way.

**Double entry in the tree (2026-10-22):** the tree reads a journal derived on
the fly from approved records (`chart_journal`), so Σ debit = Σ credit always:
a transaction debits / credits its payment method's account (1101 / 1102, each
method a row) against the account chosen; a transfer leg is only its own side;
a refund paid back debits 1103. A posted invoice: Dr 1103 total, Dr 1107 the
1% withheld (`WITHHOLDING_TAX_ACCOUNT`; Ahmed named 2104, to confirm), Cr 4101
before tax, Cr 2103 VAT; a posted refund the reverse on 4102. Columns Debit /
Credit / Balance (normal side); the tree opens collapsed to the six classes,
with search opening the branches it matches, and expand / collapse all. Still
outside the journal: supplier costs on SRs (no Finance approval step yet).

**Posting is not payment (2026-10-22, Ahmed):** posting an invoice asks only its
number and shows the entry it books (Dr 1103 + 1107 / Cr 4101 + 2103); no payment
method. The client's money is collected later with Record payment received
(Client Payment: Dr cash / Cr 1103); a posted refund is paid back with Pay back
to client (Client Refund: Dr 1103 / Cr cash). The post API still books money if
a payment method is sent.

**Daily Journal and ledgers (2026-10-22, Ahmed):** the 1% withheld is booked on
2104 (`WITHHOLDING_TAX_ACCOUNT`), not 1107. The Approved Transactions tab is the
Daily Journal (دفتر اليومية): approved transactions plus posted invoices and
refunds (shown "On account", amount muted, opening the invoice). Any row of the
Finance Tree opens its ledger (`/api/finance/tree/ledger`: every journal line
under that code or payment method, running balance, Excel).

# Mobile shell, 2026-10-26

**Ask (the client):** the system is very poor on phones. Decided with Ahmed:
an app shell (bottom tab bar + a More sheet holding every menu), every table
as one card per row through one shared mechanism, installable PWA with phone
push, everything in one release.

**Done:** see docs/milestones/07-mobile-shell.md. One phone-only stylesheet
(`bg-mobile.css`) and one script (`bg-mobile.js`) on every page; desktop
untouched. Tabs and the More sheet come from the navbar's own gated markup
(keyed on menu ids, so Arabic keeps them). Cards: cells labelled from headers,
title and actions columns picked by heuristic, overridable per table. Push:
`bg-push.js` + `/api/push/register` + `push_to_users` on every bell
notification through the app's Firebase project; `BG_FCM_VAPID_KEY` in `.env`
(read by the systemd unit) turns it on.

## Operations board: unassigned pool, 2026-10-27

David (Operations Manager): his leader and members tapped the "New Sales
Request #18921" notification and saw nothing pending. The board hid every item
not assigned to the viewer, and a fresh request has no assignments yet, so only
the Head could see what the whole department had just been told about.

Rule now (`get_operations_requests`): a restricted viewer (team / own) sees an
item while it is on nobody's desk, on their own desk, or handed out by them;
an item on somebody else's desk stays hidden. Withdrawing the last assignment
puts the item back in the pool. Tests: `OperationsListScopeTest`.

## Extra permissions and notification classes, 2026-10-27

Two requests from Ahmed.

1. **Extra permissions without a code change.** Ahmed tried to give Gamal
   `sales_request.delete` from the person modal and could not: role grants are
   generated from `rbac.SEED_MATRIX` by `seed_rbac.py`, which rebuilds
   `role_permission` on every run, so the screen was read-only on purpose.
   Plan: a second, additive layer that seeding never touches.
   - Table `permission_grant` (target_type role | department | team | user,
     target_id, permission_code, scope, granted_by, granted_at), unique per
     target and permission. A "team" is a leader and everyone reporting to
     them (`user.manager_id`), the same tree the org chart draws.
   - `load_permissions` merges the person's matching grants over the role's,
     wider scope winning. `users_holding` counts them too, so a person given
     an approval also hears about the work.
   - New permission `role.grant` (admin only, via the generated admin row).
   - API `/api/rbac/grants` (list, add/upsert, remove) and
     `/api/rbac/permissions` (the vocabulary for the picker).
   - UI: "Extra permissions" in the person modal (that person), under a
     selected role (that role), and a panel on the Roles tab for any target,
     department and team included, with the full list of extras.
   - Extras only add. Taking a role's own grant away is still a code change.

2. **Important vs Announcements.** Beshoy's tray mixes "needs you" with
   "for your information". Every notification gets `category`:
   `important` when the title asks the reader to act (approval needed,
   costing assigned / to decide, re-costing / re-pricing needed, negotiation
   to review, client approved -> source it, invoice to post / returned,
   expenses to approve, عهدة requests and hand-backs, new client / company /
   supplier requests, mentions, stock alerts, costing completed -> price it),
   `announcement` otherwise. Decided in one place (`notification_category`)
   from the title so all 48 senders are covered; a sender can override.
   - Existing documents classified once (seed), reads classify any stragglers.
   - Drawer and /notifications page get Important / Announcements tabs, each
     with its unread count; the bell badge counts unread Important only; phone
     push goes out for Important only.
   - Refined same day: Important is decided per recipient. Admins hold every
     permission, so each desk fan-out (عهدة approved -> Finance, invoice to
     post, costing completed -> pricing...) also reached them and read as
     theirs. `users_holding` / `get_users_by_role` now return an `Audience`
     whose `fyi` marks admins present only for that reason; for them it is an
     Announcement. Admin-only work (urgent approval, party requests to sign,
     their own approval chain, anything assigned to them) stays Important.
     Stored admin notifications re-classified the same way.
   - Same day: the pricing flag now carries `sales_request.delete` (all);
     Gamal's one-off person grant removed as redundant. In the person modal
     and under a role the extras box comes first and the role's own list is
     collapsed behind a toggle.

## Money inputs step, 2026-10-27

Gamal: re-pricing arrows moved a price by 0.01 (1500 -> 1500.01). 73 number
inputs carry `step="0.01"`. One script in main.html switches them, and any
drawn later, to `step="any"`: any amount is accepted and the arrows move by
whole pounds.

## Quick approval from a notification, and counts per Approvals item, 2026-10-27

Ahmed: an approval that waits on a head or admin should be decidable from its
notification, through the same flow as its approval page; once handled the
notification says Approved / Declined. And the number on the Approvals menu
must say which page it is on.

- Approval notifications carry `action` {kind, id, stage} (only for the
  people the work waits on): urgent sales request (`sales_request_approval`),
  client / company / supplier request (`party_request`), عهدة (`custody`,
  manager or finance stage), expenses (`expense`, manager or finance stage),
  negotiation to review (`negotiation`). 72 stored ones back-filled by code.
- `/get_notifications` adds each action's live `state` (pending, approved,
  declined, cancelled, gone), seen from its stage.
- `GET /api/quick-approvals/<kind>/<id>?stage=` returns the record, and the
  approve / decline URLs, which are the approval pages' own endpoints, so who
  may sign, scopes, required reasons and who is told next are unchanged.
  Finance's stages need a payment method or expense categories: the modal
  shows the record and links to the page instead.
- Tray and /notifications: "Show details" while pending; Approved / Declined
  badge once decided. Modal: details, optional notes (and the amount for a
  manager passing on an عهدة), Approve, Decline with a required reason.
- `GET /api/approvals/waiting-counts`: a count per Approvals menu item
  (expenses, client, company, supplier, sales head, account head, urgent),
  each following its page's rule; the menu badge is their total. Urgent Sales
  Requests (/approvals) added to the menu for its approvers.

## Vacant positions on the org chart, 2026-10-27

Beshoy (voice note): Kerolos, the Marketing Manager, is leaving, so that box
will be empty; under it a Digital Marketing box with two team members today
(not named). Gamal (second voice note, first misread as Beshoy's): Mariam
Magdy and Sarah Gaber, his Account Team Leaders, have nobody under them yet
but may later; should boxes go under them now? Should the chart carry boxes
for positions nobody holds? Ahmed: yes, vacant boxes (not
dummy accounts); deactivate Kerolos now; Digital Marketing is a vacant team
leader.

- `org_vacancy` (role, department, title, reports to a person or another
  vacancy). `user.reports_to_vacancy_id` puts a person under a vacancy on the
  chart; their `manager_id` stays the nearest real person above it, so
  approval chains and scopes keep working while the seat is empty.
- Org chart and PDF: vacancies drawn as dashed "Vacant" boxes; inactive
  people left off. Add / remove a vacancy, and "Fill" one with a person
  (they take its role, department and place; its reports and sub-vacancies
  move under them).
- Person modal: "Reports to" lists vacancies too; an Active switch, so
  someone who leaves is switched off rather than deleted.
- New role `digital_marketing_team_leader` (Marketing, team leader).
- Data (done 2026-10-27): Kerolos inactive (backup in private_backups/kerolos_before_deactivation_20261027.json); vacancies Marketing Manager (under Beshoy) and
  Digital Marketing Team Leader (under it). Seats under Mariam Magdy and
  Sarah Gaber wait on Gamal saying how many.
- Data (done 2026-10-28): Michael Ehab filled the Digital Marketing Team
  Leader seat (so he sits under the vacant Marketing Manager; reports to
  Beshoy until it is filled); Mira Maher and Mariam Osama added as Marketing
  Members under him. Accounts made through /api/users/add with temporary
  passwords handed to Ahmed.

## Group chats, 2026-10-27

Ahmed: three group chats beside the per-request ("code") chats, shown as
headings in the chat drawer: Managers (managers only), Operations (the
operations team only), Sales (sales only).

- Rooms decided on the server, from the person's current place: Managers =
  active people at Executive or Head/Manager level; Operations = the
  Operations department; Sales = the Sales and Account Management
  departments (nobody active sits in Sales itself; Account Management is who
  sells). A person sees and can post only in their rooms; membership follows
  role and department changes with no list to keep.
- `group_chat_message` (room, user, text, time) and `group_chat_read`
  (room, user, last message read) for unread counts.
- `/api/chat/groups` (my rooms, last message, unread), `.../<room>/messages`
  GET / POST (with @mentions, which notify like request mentions),
  `.../<room>/read`.
- Drawer: a "Groups" heading with the rooms on top, "Requests" below; the same
  thread view and composer. The chat badge counts unread group messages too,
  and keeps working for people with no access to request chats.

## Chat like WhatsApp, storage, assignment board, 2026-10-27

Ahmed: chat must be very mobile friendly and work properly in browsers; the
@ list shows only the people in that chat; photos and voice notes as on
WhatsApp; seen / not seen with "who has seen it"; a storage page in GB for
the admin; David wants to see who a leader assigned items to. Gamal (same
day): no total cost / selling / profit for Account Management on Client
Approval; Client Approval collapsible; Sarah's item photos "updated" but did
not change.

- Chat drawer rewritten into `static/js/bg-chat.js` + `static/css/bg-chat.css`
  (was inline in main.html). Desktop: list beside chat. Phone: full screen,
  one pane at a time, back arrow and the phone's back button, composer kept
  above the keyboard (visual viewport), 16px inputs, safe areas. RTL by
  logical properties.
- Members of a chat: a group = its room; a request = everyone who may write
  in it (holds `sales_request.comment`, and either their `sales_request.view`
  scope reaches the owner or they have a part in the request). Same rule now
  guards reading and writing request chats, which had no row check.
  `/api/chat/thread/<t>/members`; `/api/mention-users?thread=` and
  `/api/users/search?request_id=` give members only (drawer and the request
  page's comment boxes).
- Photos: shrunk in the browser (1600px JPEG), checked with Pillow, kept
  under `uploads/chat/<thread>/`. Voice notes: MediaRecorder, tap to record,
  cancel or send, 5 min cap; the server converts to AAC (.m4a) with ffmpeg so
  iPhones play them. `chat_attachment`, served by `/api/chat/media/<id>` to
  the chat's members only. Caption kept; lists show "Photo" / "Voice note".
- Seen: `chat_seen` (thread, user, seen-up-to, when). The drawer marks seen
  only while the chat is on screen (`?seen=1`). Ticks on my messages: one grey
  sent, two grey seen by some, two blue seen by all members. Message info
  (tap the ticks, long-press or right-click my message): seen by with time,
  not seen yet. Group unread counts moved from group_chat_read to chat_seen
  (rows carried over by `chat_media_migration.sql`).
- Storage: `system.storage` (admin), `/admin/storage` and a card on Admin
  Section: uploads by area in MB/GB, database and notifications size, server
  disk used / free.
- Operations board: each request shows who has its items, how many and who
  assigned them, plus how many are not assigned yet; the details panel has an
  "Assigned to" column (assignee, state, by whom, when).
- Client Approval: cost, profit and the money totals hidden, and cost left out
  of the data, for anyone without `sales_item.cost` (Account Management,
  Gamal included). Request cards collapse; header shows pending / approved /
  negotiating / rejected counts; Expand all / Collapse all. Dates fall back
  to the request's creation date (was 1/1/1970).
- Item photos lost on edit: the edit modal uploads a photo at once against
  the item's id, and saving deletes and re-inserts the items, cascading the
  photo away. Both edit routes now carry item files to the re-inserted item
  (same name and type). Sarah's five photos on request 23645 restored.

## Reply to a message; chat button on the operations list, 2026-10-28

- Reply like WhatsApp: swipe a bubble sideways on a phone, the reply arrow on
  hover on a computer, or Reply in the message menu (long press / right
  click; the menu also has Copy and, on my own messages, Message info). The
  quoted message sits above the composer until sent or cancelled (x or Esc);
  the sent bubble carries the quote, and tapping it scrolls to the original.
  Works with text, photos and voice notes.
- Stored as `sales_request_comments.parent_comment_id` (request chats, column
  already there) and `group_chat_message.reply_to_id`
  (`chat_reply_migration.sql`). The server keeps a reply only when the quoted
  message is live in the same chat, and sends a short preview with each
  message (`reply`).
- Operations list: a purple chat button on every request, as on Sales
  Request, with its message count and a red dot for unread mentions of me;
  it opens that request's chat in the drawer. Shown to whoever may write in
  request chats.

## Adding items to an existing request, 2026-10-27

Gamal added "Screen For VIP" to request 17593 (all 11 items costed): the save
said OK and nothing was added.

- Cause: `submitted_items` read `template_instances` / `items`, but the edit
  modal posts `template_fields.instances`. With locked items the route saw an
  empty payload: inserted nothing and reported every locked item as removed,
  still answering success. Now reads all three shapes.
- Items Operations is costing (an open costing assignment) are now locked as
  "out for costing": a sales edit used to delete and re-insert them, which
  cascaded their assignment and proposals away.
- Items added on an edit keep their comment, and Operations gets an
  Important notification "New items on request #N" with the names, linked to
  the operations page; the save message says how many went to costing.
- Gamal's lost test item was not recreated: saving it again goes through the
  normal path (insert, notification, costing).

## @all in chats; chat notifications open the chat, 2026-10-28

- `@all` (or `@everyone`): first entry in the @ list of any request chat or
  group ("Everyone in this chat (n)"). The server expands it to the chat's
  members (the same member rule as the list) minus the sender: each gets the
  usual "... mentioned you" notification (Important), and in request chats a
  mention row, so their unread @ count shows it. Typed by hand it works too;
  an address like x@all.com does not.
- Chat notifications open the chat they came from. Request mentions and
  "New comment on request #N" now link to `/home?chat=sr:<id>` (groups
  already linked to `?chat=g:<room>`); older ones are mapped from the title.
  Clicking one in the bell or on the Notifications page opens the chat panel
  on the current page instead of reloading; a phone push goes to the link and
  the chat opens there. The `chat=` parameter is removed from the address
  once used.

## Stickers and emoji in chats, 2026-10-28

- Smiley button in the composer opens a panel with two tabs. Emoji: about
  250 work-friendly emoji in five groups plus "Recent" (kept in the browser);
  a tap puts it in the text. Stickers: 20 big emoji that send on a tap, and
  the company sticker pack.
- Company pack (`chat_sticker`): anyone adds one with "+" (image shrunk to
  512px in the browser, transparency kept, GIFs untouched, 1 MB cap, checked
  with Pillow) or from a photo in a chat with "Add to stickers" in the message
  menu (only from a chat they can read). Whoever added it, or an admin,
  removes it (long press / right click in the pack); removal hides it from
  the pack, and messages that already carry it keep showing it.
- Sending: `sticker_id` on either message route makes a `chat_attachment` of
  kind `sticker` pointing at the same file. Stickers and messages of only 1-3
  emoji show big with no bubble, as on WhatsApp. Lists show "Sticker".
  `chat_sticker_migration.sql`.

## Sounds and muting chats, 2026-10-28

- Sounds made in the browser (Web Audio, no files), switched on at the first
  tap or key press as browsers require: a two-note chime when a new
  notification reaches the bell (the first load of a page is silent), a short
  pop for a new chat message (softer when that chat is open; nothing for my
  own). At most one sound per 1.5 s.
- On/off per device (kept in the browser): the speaker button in the Chats
  top bar (Message sounds, Notification sounds) and the speaker in the
  Notifications panel header.
- Mute a chat (bell button in the chat header): 8 hours, 1 week or Always;
  Unmute from the same button. Per person, on the server (`chat_mute`,
  `/api/chat/mutes`, `/api/chat/thread/<t>/mute`, `chat_mute_migration.sql`),
  so it follows them across devices. A muted chat: no sound, no pop-up, a
  bell-slash in the list, a grey unread count kept out of the chat badge. An
  @mention (including @all) still notifies, as on WhatsApp.
- Fix found while testing: the first message into an empty chat was treated
  as the chat's first load, so it neither sounded nor scrolled.

## Phone push switched on, 2026-10-28

- `BG_FCM_VAPID_KEY` set in `.env` (Firebase project brandinggate-7c1f6,
  Web Push certificate). Verified end to end with real Firebase: a browser
  gets a device token on its first visit and registers it; a push arrives as
  an in-page pop-up while the site is open and as a system notification when
  it is closed, and the tap opens its link (chats open the chat).
- Fixes found while switching it on: (1) push is now data-only; the old
  payload's `fcm_options.link` rejected our relative links, so every send
  failed, and its notification block would have shown a second copy;
  (2) the first visit waited forever for a token because the service worker
  was still installing; the page now waits for it to be active.
- What reaches a phone: Important notifications only (approvals, costing and
  pricing steps, mentions and @all). iPhone needs iOS 16.4+ with the site
  added to the Home Screen and opened from there once to allow notifications.
- Asking for permission (2026-10-28): the first page after signing in shows
  a "Turn on notifications" card (Allow / Not now); Allow opens the browser's
  own prompt from that tap, which iPhones require. "Not now" asks again after
  3 days, and every new sign-in asks until the person decides. An iPhone in a
  Safari tab (no web push there) is told to Add to Home Screen instead. The
  bell still asks on first tap as before.
- `/add_notification` (notifications written from a page) now pushes its
  Important ones too; it was the one path that never reached a phone.

## Sending a notification to anyone; wider panel, 2026-10-28

- New permission `notification.send` ("Send a notification (and phone push)
  to anyone in the system"): admin and every Executive / Head-level role
  (assistant, sales head, account director, pricing, operations, finance,
  marketing managers, 2D / 3D heads, 3D purchasing). Others can be given it
  from People & Access.
- Notifications panel: a Send button for holders. Pick people (search, or
  one tap for Everyone / a whole department), title (120), message (1000),
  and Important (default on: Important tab + phone push; off: announcement in
  the bell only). The recipient sees who sent it. `POST
  /api/notifications/send`, active people only, at most 300 at a time.
- Notifications panel widened from 460px to 640px (phones stay full width).

## Operations hear everything; app icon badge, 2026-10-29

David asked that Operations get a phone push for every notification, not only
Important ones, and for an unread badge on the Home Screen icon.

- `push_everything_ids(user_ids, link)`: the Operations department (by
  `department.code`), minus anyone who muted the chat the link opens.
  `notify_users` and `/add_notification` push to Important recipients plus
  these. Everyone else is unchanged (Important only).
- `push_to_users` adds `badge` (unread Important count, the bell's number) to
  the data payload; `firebase-messaging-sw.js` calls `setAppBadge` with it;
  `updateNotificationBadge` in `main.html` keeps the icon equal to the bell
  while the app is open, and clears it when nothing is waiting.
- Group chat messages without a mention never were notifications, so they do
  not push; tagged messages and request chats do.
- Tests: `tests/test_push_payload.py` (badge in payload, Operations-only,
  muted chat left out).

## Staying signed in on the Home Screen app, 2026-10-29

The iPhone Home Screen app asked for a password on every open: the login
cookie had no expiry (a browser-session cookie), and iOS drops those whenever
a Home Screen app is closed.

- Login sets `session.permanent`; `PERMANENT_SESSION_LIFETIME` is 30 days,
  renewed on every visit, so only 30 days without opening it signs you out.
  The cookie is `Secure`, `HttpOnly`, `SameSite=Lax`.
- The signing key was a fixed string in `branding_gate.py`, in a public
  repository, so anyone could sign a cookie for any account. It is now
  `BG_SECRET_KEY` in `.env` (random, git-ignored). The change signed everyone
  out once.
- Test: `test_contact_validation` checks the login cookie carries `Expires`
  and `Secure`.

## The job brief in costing, no money, 2026-10-29

David: costing needs everything about the request (title, dates, hotel, hall,
location, setup and dismantle dates...) and nothing about what it sells for.

- `costing_brief(row)`: title, start/end date, priority, description, notes,
  request types and every template field sales filled in (`request_data`),
  labelled from the key ("Booth_hotel_name" -> "Hotel Name"; the type is kept
  as a prefix only when the request has several). A field whose name talks
  about money (`MONEY_FIELD`: budget, price, cost, sell, amount...) is left out.
- `/api/operations/requests/<id>` returns it as `brief`, and no longer sends
  `total_sell`, item `selling_price` or item `total_sell` (the page never
  showed them, but they were readable in the browser). The list API drops
  `total_sell` too.
- `operation_request.html`: `window.opBriefHtml` shows the brief in the cost
  modal's Request Information and in the details view; two columns on phones,
  links open in a new tab.
- Tests: `tests/test_costing_brief.py`.

## The CEO in every chat, 2026-10-29

Beshoy (CEO) must be in every request chat and every group by default, and
cannot be left out.

- New permission `chat.all` (scopeless), held by the admin role ("Admin /
  CEO"), so both admin accounts have it; People & Access can give it to anyone
  else. `chat_everywhere()` = `users_holding('chat.all', include_root=True)`.
- Groups: `chat_rooms_for` returns every room for them and
  `chat_room_members` always includes them, whatever their department.
- Request chats: `chat_members` always includes them, `chat_may_open` lets
  them in, and `/api/chat/sr-list` lists every request for them.
- Membership is rule-based; there is no removal, so nobody can take them out.
  They can still mute a chat for themselves.
- `seed_rbac.py` re-run (109 permissions). Test: `tests/test_chat_everywhere.py`.

## Created by: third column and a quick filter, 2026-10-29

Gamal: in the sales request table (Sales and Pricing, the same page) show
who created each request near the front, and pick a person to see only theirs.

- `sales_request.html`: Created By moved from near the end to the third
  column (after Title); header, colgroup, column definition and the centred
  columns' CSS moved with it.
- New "Created by" picker (searchable, clearable) first in the filter row,
  filled from the people in the table; exact match on the name.
- The Status, Priority, Client and Company filters now find their columns by
  name (`status:name`...) instead of by position, so moving a column cannot
  point them at the wrong one again.
