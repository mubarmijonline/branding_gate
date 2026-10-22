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

**Values in the tree:** each account shows money in, money out and its net on
its normal side (assets, costs and expenses: out − in; liabilities, equity and
revenue: in − out), rolled up through groups and classes. Five accounts show
the live balance the system already keeps instead: 1101 the cash payment
methods, 1102 the bank ones, 1103 what clients owe (client accounts), 2101 what
we owe suppliers (supplier accounts), 1110 custody held by staff plus staff
loans outstanding. Live balances are as of now; the date filter applies to
movements.

**Reports:** the income statement and analytics roll up by group over classes
4 (revenue) and 5-6 (costs and expenses). 4101 Sales also counts posted
invoices (subtotal) and 4102 posted refunds (minus), since client payments now
go to 1103, not to revenue. The balance sheet is unchanged.

**Editing:** add an account or sub-account under any node (code suggested as
the next free one under the parent, editable, unique, must start with the
parent's code), rename, re-code and delete non-system ones. Classes and the
mapped system accounts cannot be renamed or deleted. The Categories tab shows
the same chart.
