# 01 — Costing round of client fixes

Seven comments from the client on the costing flow, 6 September 2026. Goal:
the operations desk shows each person only their own work, the Head hands out
a whole request rather than picking items, and nothing in the flow loses a
reason, a comment or a scroll position.

Status: **done, deployed 6 September 2026.**

## The seven, and what each one is

| # | Comment | What it actually is |
|---|---|---|
| 1 | Assigning lags, the page scrolls behind the modal, needs a refresh | Bootstrap 4 does not stack modals: closing the costing modal that was opened **on top of** the cost modal strips `modal-open` from `<body>`, so the operations table behind takes the scroll and the backdrop is left behind |
| 2 | The Head assigns a **whole request** to a team leader; the leader does the per-item split | Assignment is per item only. Add a request-level action that fans out to every item, so the existing per-item rules keep working underneath |
| 3 | Costing can add an **alternative option** — image plus comment — behind the main image | New: a flag and a comment on `sales_request_item_images` |
| 4 | Clicking a notification must open the page where the action is | Notifications carry no link |
| 5 | Item comment must be visible in the add-cost modal without expanding | The comment is inside the collapsed body |
| 6 | Operations page must show only requests assigned to me, or with an item assigned to me | `/api/operations/requests` has no scoping at all — everybody sees every request |
| 7 | A rejected proposal reaches its author without the reason | `costing_for_request` selects `decision_note` and then drops it before the JSON |

## Order of work

1. **Modal stacking** (1) — template only, unblocks the rest of the testing.
2. **Item comment always visible** (5) — template only.
3. **Rejection reason** (7) — one field through the API, rendered.
4. **Assign a whole request** (2) — new endpoint, fans out per item.
5. **Scope the operations list** (6) — depends on 2 being the way work arrives.
6. **Notification links** (4).
7. **Alternative options** (3) — migration, endpoints, UI.

## Rules that do not change

- Assignment still goes to **direct reports only**; the Head still overrides.
- The **leader who asked** still decides the proposals they asked for.
- Accepting a proposal is still the only thing that writes `cost_per_item`.
- Scope stays `costing.view`: `all` = Head sees everything, `team`/`own` see
  what passes through them. No new permission is invented for item 6.

## Done means

- Assigning from the cost modal leaves the scroll where it was, no refresh.
- David picks a request and a leader; every item on it lands on that leader.
- A leader opening `/operation_request` sees only requests they are part of;
  a member sees only requests holding an item assigned to them, and the item
  counts on those rows count only their items.
- A rejected author sees the reason.
- Clicking a costing notification opens `/operation_request`.
- An alternative image with its comment shows on the item, marked as one.


## What was built

| # | Where |
|---|---|
| 1 | `operation_request.html`: two delegated handlers raise a stacked modal and its backdrop, and put `modal-open` back when a modal closes over another. The table redraw is deferred to modal close instead of running behind the dialog. |
| 2 | `POST /api/costing/assign-request` fans a request out to a row per item; an **Assign** button on each row of the operations table. |
| 3 | `costing_alternatives_migration.sql` adds `is_alternative`, `alt_comment`, `alt_label` to `item_images`; `GET/POST /api/costing/items/<id>/alternatives` and `DELETE /api/costing/alternatives/<id>`; shown in the cost modal and in the sales request drawer, excluded from `attachments` in all three readers. |
| 4 | `notify_users(..., link=...)` stores a destination; the bell and the notifications page navigate to it; `notifLink()` derives one from the words for the 1800-odd notifications already in the tray; `?request=N` opens that request on `/operation_request` and filters to it on `/pricing`. |
| 5 | The item comment moved out of the collapsed body into an always-visible strip under the summary chips. Both copies are now escaped. |
| 6 | `/api/operations/requests` scopes on the viewer's `costing.view`, with the counts and the total computed over their items alone. |
| 7 | `costing_for_request` returns `decision_note`; the proposal table renders it under the state, and says "No reason given" when the decider left none. |

## Tests

23 new, in `tests/test_costing.py` (whole-request assignment, list scoping,
rejection reasons, alternative options) and `tests/test_template_javascript.py`
(where each kind of notification leads). The costing fixtures were split out of
`CostingChainTest` into `_CostingHarness` so reusing them does not re-run the
chain. Suite: **201 passing**.

## Follow-up round, 6 September 2026

Two more comments, both cross-cutting rather than about one screen.

**Who did it.** Tables showed `01017780012` under "Created by". That is
`user.username`, which on this system is a mobile number, and it is not a name
anybody reads. The underlying problem is that the columns disagree: five routes
wrote five different things into them (mobile, display name, login name, user
id, and in one case the literal string `password reset`). Rather than migrate
five kinds of history, `people_index()` + `person_of()` resolve whatever is
stored back to the person on the way out, and the lists show the name with the
mobile under it and the user id on the element. Verified against every shape
present in the database.

**Numbers.** `EGP 292975` now reads `EGP 292,975.00`. One shared helper
(`static/js/bg-numbers.js`) replaces four copies of the grouping logic and a
dozen places with none, applied to 26 amount renderers across 8 templates plus
the sales table's own columns. Amount fields group as they are typed — unit
cost, costing proposal, sell price, both expense amounts — and every reader of
those fields strips the separators, because `parseFloat("1,250")` is 1 and that
would have been a silently wrong total. Proven on the live site: typing
`1250000` into a unit cost shows `1,250,000`, computes `40,000,000.00`, and
posts `40000000.00`.

## Third round, 6 September 2026

**Only team leaders for a whole request.** The dialog offered everyone in
Operations, including the inactive seed accounts, so the Head could hand a
whole request straight to a member and skip the leader whose job the split is.
`/api/costing/team?leaders=1` filters to `LEVEL_TEAM_LEADER`, and both forms of
the list now skip `is_active = 0`.

**The cost modal, revamped.** Eleven items meant a long scroll of near-identical
cards, each printing "not assigned" and "No proposals yet", and assigning them
meant eleven dialogs and eleven round trips. Now:

- a sticky toolbar with the counts (`11 items · 0 costed · 11 waiting · 11
  unassigned`), filters for **Not costed / Unassigned / On my desk**, and a
  select-all;
- a checkbox per item and one **Assign** button that sends the lot in a single
  request — `/api/costing/assign` takes `item_ids`, and a bad id in the list
  assigns none of them;
- an untouched item is quiet: no empty proposal table, no "not assigned" line
  where a button already says so.

Measured while doing it: the modal opens in ~3s on 11 items, the server calls
behind it take 85ms and 55ms, the DOM stays at ~1,750 nodes across repeated
open/close cycles, no backdrops accumulate and the event loop stays under 5ms.
All four ways of dismissing the stacked dialog — Cancel, ×, Escape, backdrop —
leave the cost modal open, the scroll locked to it and the fields usable.

## Fourth round, 6 September 2026

**The modal was dead, not hung.** The previous fix raised every backdrop that
was not yet marked, which took the cost modal's *own* backdrop (1040) up to
1060 -- above the modal itself at 1050. The modal stayed drawn and fully dimmed
and every click landed on the backdrop. Only the backdrop of the modal being
opened is raised now. Caught by asking `document.elementFromPoint()` what a
mouse would actually hit; the previous check used `focus()`, which works
straight through an overlay and reported a dead modal as usable.

**An empty request offered work that did not exist.** A LEFT JOIN gives a
request with no items one row of NULLs, and `cost_per_item IS NULL` is true of
it, so request #786 -- raised with the Event template's fields filled in and no
items -- counted one item pending and offered an "Add Costs" button that opened
an empty modal. Both counts now require `i.id IS NOT NULL`; the row reads
"No Items" and carries no button. If the modal is reached anyway it says why it
is empty and hides the toolbar, the total and the save button.

## Fifth round, 7 September 2026

**A notification's filter has to be visible and undoable.** `?request=784`
narrows the table to that one request so the reader lands on the work they were
told about. Once the modal is closed that narrowing is invisible -- the table
just looks like it has lost every other request. Both deep-linked pages now
carry a notice, "Showing request #784 only", with a **Show all requests**
button that releases the table search and takes `?request=` out of the address
so a refresh does not drop the reader back into it. On the operations page the
status cards and the status dropdown release it too, since picking one of those
means leaving the single request behind.

## Sixth round, 7 September 2026

**A costed item is finished, and the page now says so.** The edit route
protected costed items by skipping *every* item change on the request and
returning "updated successfully" -- so an edit to the ten items still open was
thrown away because the eleventh had been costed, and nothing said a word about
it. That is the "it shows updated but the backend did not update" report.

- `item_lock_reason()` is the one definition of finished: **priced**, then
  **costed**, then **with the client**. The edit route and the edit form both
  read it, so they cannot disagree.
- The route now edits the items that are still open and leaves only the locked
  rows untouched, then reports `locked_items` and `refused_changes` -- which
  item, why, and which fields the edit tried to change.
- The edit form marks a locked item read-only with the reason on it, so nobody
  types into a field whose value is going to be discarded.
- Saving says either "Saved, with some items left as they were" and names them,
  or "Request updated. N items are locked and were left as they are."

Also found and left alone for now: `/api/sales/requests/edit/<id>` has no such
protection and deletes items before re-inserting them without their costs. The
UI does not call it -- it posts to `update-with-template` -- but it is reachable
and it destroys costs. Worth closing next.

## Seventh round, 7 September 2026

**The costing loop was silent at every hand-off.** A price arrived and the
leader who asked for it was never told; it was declined and the member found
out by opening the page; it was sent again after a refusal and nobody knew. All
four now notify, each carrying a link to the request:

| What happened | Who hears it |
|---|---|
| A price is put up | the leader who asked for it |
| A price is put up **again** after a decision | the same leader, worded as a re-submission |
| A price is declined | its author, **with the reason**, or "No reason was given" |
| A price is accepted | its author, and everyone whose price lost |

Five tests capture the calls and assert the audience, the wording and the link.

**The operations table says which request a row is.** Title and Company sit
beside Client Name. The status filter now finds its own column by name instead
of counting to 2, which inserting two columns would otherwise have pointed at
the client.

**Pricing shows what a price is worth as it is typed.** Gross, Markup % and Net
% sit under the sell-price field -- the numbers already existed further down the
card, where they were no use to whoever was typing. Under cost reads **below
cost** in red, under 10% net reads **thin margin** in amber, and clearing the
field puts the strip back to neutral.

## Eighth round, 7 September 2026

**The pricing modal's totals had never rendered for anybody.** The footer showed
only "Total Selling Price" because the block holding Total Cost, the difference
and the percentages was gated on `{% if is_admin %}` -- a variable this template
is never given. Undefined is falsey in Jinja, so the branch was dead for every
user including admins, and the numbers behind it were computed only for
`isAdminUser`.

Now gated on `sales_item.cost or sales_item.price`, which is who already sees
every item's cost inside that same modal, and the totals are computed whenever
the summary is on the page. Three boxes rather than four: "Difference" and
"Net Profit" were the same number under two names.

    TOTAL COST      EGP 282,700.00   Markup 42.6%
    TOTAL SELLING   EGP 403,050.00   Net margin 29.9%
    DIFFERENCE      EGP 120,350.00   Markup 42.6% · Net 29.9%

Markup is against cost, net is against the selling price. The difference badge
goes amber under 15% net and red below cost.

## Ninth round, 7 September 2026

**The Operations Head could not add an entity.** `/entity-management` offered
an "Add Entity" button to anyone holding `entity.view`, and the route behind it
wanted `entity.create`, which only admin had. `operations_manager` now holds
`entity.create` and `entity.edit` -- they already create the suppliers and the
inventory an entity holds. Deleting one is still admin-only: it takes its
inventory with it. Every button on that page is now gated on the permission its
own route enforces, so the class of bug (button offered, action refused) is
closed rather than the one instance of it.

**The status dropdown was drawing its value clipped.** The page's own
`.form-control` rule adds 12px of vertical padding, which a `<select>` takes on
top of Bootstrap's fixed height, so the chosen option was pushed out of its own
box. Selects now size to their content with room set aside for the arrow.

**Supplier requests were missing from the Approvals menu**, which is where the
Head decides them -- client and company requests were there, supplier was not.
Added, and all five party-request notifications now carry the page they are
about (`/client`, `/company`, `/supplier`) instead of leaving the tray to guess
from the words.

## Tenth round, 7 September 2026

**`@` did nothing because the list behind it was a 403.** The comment boxes
loaded `/api/users` -- the account-management list, gated on `user.view`, which
only admin holds. Everyone else got 403, `mentionUsers` stayed empty, and
typing `@` had nothing to offer. Tagging a colleague is not administering them,
so it has its own endpoint: `/api/mention-users`, gated on
`sales_request.comment`, returning active people with their name, role and
department and no contact details at all. David now gets 11 names where he got
a 403.

**Nothing was ever notified about a comment.** The route did
`INSERT INTO notifications` -- a MySQL table that does not exist on this system,
because notifications live in Mongo behind `notify_users()`. The insert raised,
the surrounding `except` swallowed it, and not even an explicit @mention
reached anybody. Now:

- a mention notifies the person named, titled "X mentioned you";
- everyone else with a part in the request gets "New comment on request #N" --
  the owner, whoever it is assigned to for costing, whoever assigned them, and
  anyone already in the thread;
- the author is left out, a mentioned person is not told twice, and every one
  of them opens the request.

Nine tests in `tests/test_request_chat.py`, including that the mention
directory carries no mobile, email or password state and that an inactive
account cannot be tagged.

## Eleventh round, 7 September 2026

**The Head was being asked to raise a request he would approve himself.** He
holds `supplier.create` *and*, by being in Operations, `supplier_request.create`
-- so the page showed him both paths, with the request card sitting above the
Add button. The request flow is now hidden from anyone who can add the party
outright, for clients and companies as well as suppliers. The card stays: it is
also where he decides what his team asks for, and it now says so.

**A supplier's email is optional.** It was demanded in four places at once --
`PARTY_REQUIRED`, the request form, both supplier forms, and a `NOT NULL`
column -- so the address being typed was frequently a placeholder. Two suppliers
on the live system share one. `supplier_email_optional_migration.sql` makes the
column nullable; an email that *is* given is still validated for shape and
still checked for duplicates, and two suppliers with no email are no longer
duplicates of each other.

## Twelfth round, 7 September 2026

**The supplier email was demanded in three more places.** The last round made
the column nullable and dropped the rule from the routes, but three
client-side checks were still refusing to save: the supplier form, its edit
form, and a fourth copy in the shell's quick-add supplier dialog. All three are
gone, along with their `required` attributes and red asterisks. The client's
quick-add still requires one -- only the supplier rule changed. The edit route
also no longer treats an emptied field as a duplicate collision.

**Deleting an inventory item flickered between two versions of the truth.**
None of the JSON APIs sent cache headers, so after a delete the browser was
free to answer the table's reload out of its own cache: the deleted row came
back, and the next reload showed it gone. One `after_request` hook now marks
every `/api/` GET `no-store`; pages and static files keep their own caching.
The delete also awaited nothing -- it fired three reloads and reported success
immediately, over a table still showing the old rows. It now waits for them,
which needed the three loaders to return their promises at all.

**The Operations Head may delete an entity.** The safety was never the grant:
the route refuses any entity that still holds inventory, whoever is asking.

## Thirteenth round, 8 September 2026

**"Other" was being stored as the type.** Choosing Other and typing
"Production" stored the literal word **Other**, with "Production" parked in
`other_supplier_type` -- a column no list, filter or report reads. Both
suppliers on the live system that had a real type were showing as "Other".

`resolve_supplier_type()` is now the one place that decides: the typed word is
the type, and it is kept in the second column too, as a note of how it arrived.
`supplier_type_backfill.sql` corrected the two existing rows -- both now read
**Production**.

**A typed type is offered from then on.** `/api/suppliers/types` returns the
built-in list merged with every type anybody has actually used, and both
dropdowns are built from it and refreshed after each save. No table to
administer and nothing to keep in step with the data: a type exists because a
supplier has it. "Other" is no longer offered as a type at all -- it is the
control that reveals the text box, and reads "Other (type your own)".

## Fourteenth round, 8 September 2026

**"Deleted successfully" over an item that was still there.** An inventory item
with movements behind it cannot be removed -- the transactions refer to it --
so the route retires it, marking it `discontinued`. It then reported "Item
deleted successfully". And `get_inventory_items` **ignored the `status`
parameter the page was sending**, so the retired row came straight back into
the list under "All Status", and the low-stock and out-of-stock filters had
never done anything either. The one item on the live system was already sitting
there discontinued, exactly as reported.

The route now says which of the two things it did, the page says "Item retired"
and explains why, the filter honours `status` (with "All" meaning every item
you still have), and a "Discontinued" option makes a retired item findable.

**Every page hanging had its own cause: 228 routes leaked their connection.**
Each opened one inside `try` and returned from `except` without closing it. A
few hundred errors exhausts MySQL's 151 connections and every request then
blocks waiting for one that is never returned. Rather than patch 228 handlers,
`connection()` registers what it hands out against the request and a
`teardown_request` closes anything still open, however the handler left.
Measured: 50 requests, no change in `Threads_connected`.

**Editing an entity from its own inventory page.** It was reachable only from
the entity list, so changing the name of the thing whose stock you were looking
at meant leaving the page. There is an "Edit Entity" button on the inventory
header now, and `/entity-management?edit=<id>` opens that entity directly.

## Fifteenth round, 9 September 2026

**The Actions menu jumped from below the button to above it.** Bootstrap draws
a dropdown downward and Popper re-places it on the next frame when the row is
near the bottom of the scroll box, which reads as the menu flickering into
place. Three actions do not need a menu: the inventory rows now carry plain
buttons, the same shape the entity table has always used. The credit rows had
the same menu and got the same treatment.

**A minimum typed while adding an item was thrown away.** The form posts its
field names verbatim, and it posted `min_quantity` while the route reads
`minimum_stock_level` -- so the value vanished and only stuck once somebody
went back and edited the item, which is exactly how it was reported. The unit
had the identical bug (`unit_type` posted, `unit_of_measure` read), so every
item created here became PCS whatever was chosen. Both names now match.

**The tiles announced zero before they had counted.** They were hard-coded to
`0` and `EGP 0`, so every load showed a confident "you have none" until the
fetch landed and all four figures jumped -- the flash that reads as lag. They
now start blank and are revealed together the moment they are known. The
count-up "animation" that ran afterwards is gone: it read the value it had just
been given and spent 600ms in thirty frames counting from that value to itself.
