# Branding Gate - functional PRD

What the system does, for whom, and how "done" is checked. Behaviour only:
how it is built lives in `docs/PLAN.md`. The sales request journey (request,
costing, pricing, client approval, negotiation) is described in
`docs/sales-request-journey.md`; sections are added here as features are
specified.

## Design Requests

Asked for by Gamal Gaber (Design), 28 Oct 2026, with the "Design Request
System" map he sent.

### Who uses it

| Role | What they do |
|---|---|
| Account Manager / Sales (requester) | Opens a design request for a client, follows it, and when it is approved sends it to Operation. |
| Design head (2D or 3D) and Design Manager | Sees every incoming request and assigns a designer. |
| Designer (2D or 3D) | Sees the requests assigned to them, uploads the work (PDF, JPG/PNG, or a link) and submits it for approval. |
| Design Manager | Approves the work or sends it back with a note. Approving is a Design decision: it is not done as Account Director. |
| Operations | Sees the requests sent to Operation and opens their files, to execute. |
| Admin | Everything. |

### Screens and flow

1. **Design Requests page** (Sales / Account menus, and the 2D and 3D Design
   portals). A list of requests the person may see, newest first, with
   2D / 3D and status filters. 2D and 3D are one list with a column, not two
   copies.
2. **New design request** (requesters):
   1. Header shared by the whole request: Company, Client, Job code (an
      optional Sales Request of that client the requester can see), Event
      Date, Deadline, and 2D or 3D.
   2. Category tabs: Social Media, Printing & Production, Video, Mockup &
      Reference, Identity, Presentation, Other.
   3. "Add item" on a tab adds an item of that category with its fields.
      Several items, of any categories, in one request.
   4. Every item: Request Title, Deadline (defaults to the request's),
      Attachments (picked as many times as needed, from different folders,
      each removable before submit), Description. In addition:
      - Printing & Production: Size (cm) H x W x L, Quantity and unit (the
        same units as a sales request item), Type of Printing (Vinyl, Banner,
        Laser, Digital, Silkscreen, UV).
      - Video: Size H x W, Duration.
      - Other: every field above.
   5. Submit. Until then nothing is saved.
3. **Request detail**: header, items with their fields and attachments, and
   under each item its state, its work (the round handed in, what is not
   handed in yet, earlier rounds) and the buttons for that item; the history
   (who did what, when) and the request's buttons at the bottom.

### Workflow and rules

Each item (Gamal, 30 Oct 2026):

```
open --designer submits the item--> in review --approve--> approved --send--> sent
  ^                                     |
  +-------- changes requested <---------+
```

The request: waiting for a designer until one is assigned; then waiting for
approval while any item is in review, changes requested while any item is
returned, approved once every item is approved, sent to Operation once every
item is sent; otherwise with the designer. Cancelled by the requester only
before any work was handed in.

- A request needs a client, an event date or deadline is optional, and at
  least one item with a title.
- Only design heads and the Design Manager assign; they may reassign until
  the work is approved.
- Only the assigned designer uploads work, to one item, and submits that
  item, only with new work since its last round (a file or a link). Handed-in
  work cannot be removed; it stays as an earlier round.
- Only the Design Manager approves an item or asks for changes; asking for
  changes needs a note and returns that item to the designer.
- Only the requester (or someone above them in Sales / Account) sends the
  approved items to Operation, as soon as any are approved.
- Operations sees the sent items with their final round only: no drafts,
  earlier rounds, attachments of the brief, or history, and cannot open
  those files by link.
- The requester may cancel until a designer has handed in work.
- Each step notifies the next person: Design on submit, the designer on
  assign and on changes, the Design Manager on submit for review, the
  requester on each approved item, Operations on send.
- A requester sees their own requests (a team leader their team's, a head
  their department's); Design sees all; Operations sees only those sent to it.
- Files: PDF, images, Office and design files (AI, PSD, EPS, ZIP), up to 20 MB
  each; a photo opens in the
  viewer.

### Out of scope (for now)

- A library of client assets (logos) reused across requests: recommended,
  not built. See PLAN.md.
- Separate 3D categories and fields: 3D uses the same seven until Gamal's 3D
  map arrives.
- Assigning different items of one request to different designers.
- Turning a design request into a sales request automatically.

### Done when

- `tests/test_design_requests.py`: the whole flow by the right people, each
  step refused to the wrong ones, category fields kept per category, scope
  (requester sees own, Operations only sent ones), files readable only by
  who may see the request.
- Browser at 390px and 1440px: create a request with a printing item and a
  video item and attachments, assign, upload, approve, send to Operation,
  each as the right user.

## Costing hand-off to Pricing

Asked for by David Osama (Operations Head), 28-29 Oct 2026.

- A cost saved by Operation stays with Operation. Pricing sees an item, its
  cost and a place to price it only once a Team Leader or the Head sends it.
- Two ways to save: "Update Item Costs" saves only; "Update and Send to
  Pricing" saves and sends every item not yet sent, in one click. If some
  item still has no cost, the costs are saved and nothing is sent, with the
  reason shown.
- A cost of 0 is a valid cost: the item counts as costed, keeps its 0 and
  can be sent to Pricing like any other. Only an empty cost means not costed.
- A selling price of 0 is valid too (free items): the item counts as priced,
  goes to the client and shows on the quotation at EGP 0. A negative price is
  refused; only an empty price means not priced.
- Part of a request can go early: pick costed items in the cost window and
  "Send N to Pricing". Those items are with Pricing; the rest stay with
  Operation and are sent later ("Send the rest to Pricing").
- On the Pricing window an item not sent yet reads "Still with Operation",
  shows no cost and cannot be priced. The request totals stay hidden from
  Pricing until every item is sent.
- A cost changed on an item Pricing already has keeps it with Pricing, marks
  the request "Cost changed" and tells Pricing. Costing an item Pricing does
  not have yet is not a change.
- An Operations Team Leader sees and decides the costing of their own team's
  members, including items the Head handed to a member directly.
- The Pricing window opens with the request's General Details (title, client,
  company, request types, dates, duration, created by, description) and each
  template's fields (place, governorate, hall, hotel, setup and event dates,
  map link), the same values the request details page shows. The panel folds
  away.

Done when: a request with 10 items can have 3 sent and priced while 7 are
costed; the Team Leader of a member the Head assigned to sees the request
and can accept that member's price.

## Editing items, and re-costing after a change

Asked for by Gamal Gaber (Sales), 30 Oct 2026.

- Sales can change an item freely until Operations has costed it, including
  while it is out for costing. The person costing it is told what changed.
  Adding or removing items never touches the others.
- Once costed (or priced), an item's name, quantity, unit, sale or rent,
  days and dimensions cannot be changed directly. "Change and re-cost" on
  that item lets Sales change it with an optional note for Operations; on
  saving, its cost and price are cleared, it leaves Pricing, it goes back to
  whoever costed it, and Operations is told. It shows "Re-cost requested"
  everywhere until Operations costs it again.
- "Change and re-cost" opens inside the item card, not as a pop-up: it says
  what will happen, takes the note, and nothing changes until Update Request.
  The Operations Head and team are notified with the note, and the request
  shows "Re-costing" on the Operations list.
- The Calc ticks (count the days, count the quantity) can be changed on a
  costed or priced item without a re-cost: the unit cost and price stay, the
  totals are recalculated, and Pricing and Operations are told.
- An item the client has already approved cannot be re-costed this way; it
  goes through negotiation.
- A request created through the urgent-date approval opens in the edit form
  with all its items and place fields, like any other request.
- In the edit form each item is one collapsible card: name, quantity and
  size on the header line, with its stage (New, Not costed yet, With
  Operations, Costed, Priced, Re-cost requested). In the request details
  (Sales and Pricing) items are one line each with quantity, stage and selling
  total, opening on click, with Expand all / Collapse all; the activity list
  shows the latest entries with "Show all". The Pricing window says how many
  items are left to price and can show only those.

Done when: adding an item to a request whose items are all costed keeps every
item; a costed item changed through "Change and re-cost" returns to
Operations without its old cost and price, and leaves the mark when costed
again.

## Client Approval page: who created the request, and staying in place

Each request on the Client Approval page shows who created it, next to the
client. The filters include "Created by", listing everyone behind the requests
the other filters leave. Approving, rejecting or negotiating an item keeps the
reader where they were: same scroll position, same page and search in that
request's item table, so the next item can be decided straight away.

## Targets by month, and what makes up Achieved

A quarter's target can be spread over its three months unevenly (more in one
month, less in another); the three months always add up to the quarter's
amount, and an amount with no split is spread evenly. The quarter table has a
column per month: what the person (and the team under them) reached that
month against that month's target, with the current month marked. What a
leader handed down and what is still free sit under their target.

Clicking a person's name or Achieved number opens their report, for any
department (the page follows the reporting line):
- achieved against target, what is waiting on the client, and what is still
  to reach, with the amount needed per month left;
- month by month;
- where the target came from: each person above them the viewer may see,
  their target, the share handed down, who set it, when, and the note;
- the team under them, each linking to their own report;
- every request of theirs (or their team's) in the quarter, with what is
  approved (counts), waiting on the client, and rejected, its stage, and
  filters for each; approved always adds up to Achieved;
- clients by approved value, and the year quarter by quarter;
- Print / Save as PDF.
Someone sees only the reports their target scope covers.

## Urgent requests reach the Operations team leaders

When an admin approves a request with an urgent date, the Operations Head is
told as for any new request, and every Operations team leader is told too, so
a leader can assign its items to their own people for costing straight away.

## Request numbers

Sales requests are numbered in one sequence, starting at 502, in the order
they are created. The numbers do not skip.

## Paying supplier purchases by request

- Finance > Suppliers lists Purchases by request: for each sales request and
  supplier, what was bought (the client-approved items costed with that
  supplier), what was paid against that request, and what remains. Unpaid
  first; "Unpaid only" can be cleared to see paid ones. Each supplier's
  statement shows its own.
- Someone who can approve Finance transactions pays from the request: chooses
  the payment method, the amount (defaults to what remains), date and
  reference. A cash method posts on its row under 1101 الخزينة, a bank method on
  its row under 1102 البنك, against 2101 الموردين.
- A payment against a request cannot be more than that request still owes the
  supplier. A payment without a request stays a payment on the supplier's
  account.
- Only Finance sees these pages; no cost reaches Sales.

Done when: George pays part of an SR's purchase from a bank and the rest from
cash; the request's remaining drops to zero, the bank's and the cash box's
ledgers show the payments, and paying more is refused.
## Staff expenses paid to suppliers, and supplier accounts under 2101

- An expense on My Expenses names who was paid: Transportation, or a supplier
  from the list Finance keeps. A name cannot be typed; a supplier not in the
  list is added under Suppliers first. A supplier is shown everywhere by its
  company (Royal Vision), with the person after it.
- The supplier list follows the chosen sales request: Transportation, then
  "On this SR" (the suppliers Operations assigned to that request's items),
  then every other registered supplier. Any registered supplier can be chosen.
- Every expense carries at least one receipt or document. Without one it
  cannot be saved from the form, sent for approval, or approved by Finance.
  Until Finance decides, the owner can add a document to an expense already
  sent (paperclip on the line), and cannot remove the last one.
- On Finance's approval list each line shows its documents (thumbnails, open
  in a click, or a red "No document"), and for a line paid to a supplier what
  that request owes the supplier (client-approved item costs), what was paid,
  what remains, with a warning when the line is more than what remains or the
  supplier has no approved items on that request.
- A line paid to a supplier needs no category: it goes to 2101 on that
  supplier's own account. Every supplier has one, numbered as they are added:
  21011, 21012, ... A code once given never changes.
- In the Finance Tree, 2101 lists every supplier account; 2101 is their sum.
  An account is owed the cost of the items Operations assigned to that
  supplier once the client approved them, and paid by every payment to them
  (Finance's own and staff expenses). Opening a supplier shows a large report:
  total owed, paid and the number of payments, remaining; the same by
  request with the items; every payment; the full statement; Excel.

Done when: Ahmed's expense to Royal Vision on SR-502 cannot be sent without a
receipt; Finance sees the receipt and SR-502's owed/paid/remaining for Royal
Vision on the line, approves it without choosing a category, and 21011 Royal
Vision in the tree shows the payment against what SR-502 owes.

- Whoever asks for money (Expense Tracking) does not choose where it comes
  from. Finance chooses the payment method when approving, and cannot approve
  without one.
- The Operations home page opens with My Money Requests (request balance,
  submit an expense reimbursement, spend from my balance, my requests, and the
  person's balance) for those whose requests go straight to Finance: the head
  and the admin. Each tile shows only to those allowed to use it. Others still
  find the same actions in the balance menu.

## Client accounts under 1103

- Every client has its own account under 1103 العملاء, numbered as they are
  added: 11031, 11032, ... A code once given never changes.
- In the Finance Tree, 1103 lists every client account and is their sum: a
  posted invoice is a debit on the client, a collection from them a credit, a
  refund the reverse.
- Opening a client shows a large report like a supplier's: approved sales,
  invoiced, collected (number of collections), outstanding (approved, not yet
  collected), balance due; the same by request; every collection; the full
  statement; Excel and the account page.
- A collection is money posted to 1103. The custody leg of an approved staff
  expense names the client but is no money from them, and is not counted.

Done when: every client row under 1103 carries its code, 1103 equals the sum
of its clients, and each client's balance equals their statement.

## Supplier assignment approved by Finance; agreed and actual cost

- Only the Operations head and team leaders assign a supplier to an approved
  item. Assigning (or changing, or removing) is a request: the supplier, the
  actual cost, the due date, a note, and at least one document (quotation,
  invoice, agreement). Nothing changes on the item until it is approved.
- The item's costing is the agreed cost. The actual cost starts at the agreed
  cost and can be changed. At or below agreed the request goes to Finance.
  Above agreed it needs a reason and goes first to the Operations head (David)
  under Approvals > Supplier Cost Approvals, then to Finance. The head's own
  request above agreed goes straight to Finance.
- Finance approves under Finance Approvals > Supplier Assignments, seeing the
  documents, the actual cost (what becomes owed), who approved the cost, and
  what the request already owes that supplier. Finance never sees the agreed
  cost: it would mislead it (only Operations and the head see it). On approval the item is with the supplier
  and the actual cost is owed to them (their account under 2101); the agreed
  cost stays on the item. Declining needs a reason; the requester is told.
- Each item row on Approved Items shows its request under the supplier:
  waiting for the Operations head or for Finance (with the supplier asked
  for), or declined with the reason.
- The assignment window shows the supplier now (with agreed and actual cost),
  a request waiting (with its files, withdrawable), the request form, the
  delivery dates, and every past request with its decision.

## Deciding Finance approvals from the notification

- Every Finance approval sends a notification that opens the full record:
  supplier assignments, supplier costs above agreed (to the head), custody
  requests, expense reimbursements, each My Expenses line sent to Finance, and
  transactions waiting for approval. The window shows all the data, the
  receipts and documents, and what Finance must choose (payment method, the
  account per line); Approve and Decline work there, with the same rules as the
  approval pages.

## Client invoice Tax ID

- Posting a client invoice (or refund) asks Finance for its Tax ID, the number
  the tax authority gave the e-invoice. It cannot be posted without one, and a
  Tax ID belongs to one invoice only.
- The Tax ID shows on the invoice list and window, on the printed invoice, on
  the journal entry (Finance Tree ledger) and on the client's statement.

## Finance Approvals page

- One page for everything waiting on Finance. On top, a box per kind (staff
  expenses, supplier assignments, custody requests, expense reimbursements,
  transactions) with how many wait and their total; a box opens its list.
  "Money is paid from" is chosen once for the page.
- Staff expenses: one card per person (how many lines have a receipt and how
  many do not), one row per line: code, date, description, SR and client, who
  was paid (a supplier with its 2101 code and what the SR owes them), the
  receipt (opens in a click), the amount (editable), the account (6212 preset
  for Transportation; supplier lines need none). Approve or decline a line with
  its own buttons, or tick lines and use the bar at the bottom. A line without a
  receipt cannot be ticked or approved. Search, "only lines with a receipt" and
  "account for every line" help with many lines. A line whose SR no longer
  exists says so and is approved without the link.
- Custody requests and transactions: one row each with who it is for, what
  they hold now, who approved it before, the account and payment method;
  Pay out / Approve and Decline in place.

## Trial balance

- Finance Management has a Trial Balance tab (ميزان المراجعة): monthly,
  quarterly, yearly, or any two dates. For every account of the Finance Tree
  (classes, groups, accounts, each payment method under 1101/1102, each
  supplier under 2101): the opening balance on the first day, the period's
  debits and credits, and the closing balance on the last day, each balance on
  the side it falls. Groups add up the accounts under them; totals at the
  foot, with a debit = credit check.
- Rows can be shown to a level (classes, groups, accounts, all), folded by
  group, zero rows hidden or shown; Excel (Arabic, right to left) and print.

Done when: November's closing balances equal December's opening balances, and
every column's debit total equals its credit total.
