# Branding Gate

Internal ERP: sales requests → costing → pricing → client approval → negotiation →
operations handoff, plus inventory, finance and expenses.

- **Live:** https://bg.mubarmijonline.com (gunicorn + nginx, systemd `branding_gate.service`)
- **Repo:** https://github.com/mubarmijonline/branding_gate — **public**
- **Code:** `branding_gate.py`, one Flask file, ~22k lines, 246 routes. Templates in `templates/`.
- **DB:** MySQL `branding_gate`, raw MySQLdb via `connection()` at the top of `branding_gate.py`

## Running things

```bash
./branding_gate_VENV/bin/python -m py_compile branding_gate.py     # syntax
sudo systemctl restart branding_gate.service                       # deploy
```

**pytest is not installed.** Tests are unittest:

```bash
PYTHONPATH=.:tests ./branding_gate_VENV/bin/python -m unittest \
  test_rbac test_scope test_route_coverage test_hierarchy_admin \
  test_password_hashing test_template_javascript test_negotiation_workflow \
  test_negotiation_templates test_negotiation_routes test_sales_request_journey_pdf \
  test_targets test_portals test_costing
```

169 tests. `tests/test_design_system.py` is pytest-style (bare functions) and is run by
calling its `test_*` functions in a loop.

## Access control

Authorization is `rbac.py` (pure policy, no Flask/MySQL) plus wrappers in `branding_gate.py`.

- **89 permissions** as `resource.action`; **21 roles** across 4 levels (0 exec → 3 member);
  `SEED_MATRIX` maps role → {permission: scope}. Edit it, then run `seed_rbac.py`.
- **Scope** is `own | team | department | all`. `team` = self + direct reports
  (`user.manager_id`); `department` = same `user.department_id`. Nobody sets scope by
  hand — it follows the reporting line.
- **Gate a route** with `@perm('some.permission')`. Never invent a permission string:
  `perm()` raises at import if it is not in `rbac.PERMISSIONS`.
- **Filter rows** with `scope_clause(code, column)` → `(" AND col IN (%s,%s)", [ids])`,
  or `assert_scope(code, owner_id)` on a detail/mutation path.
- **Default deny:** `require_login` refuses any endpoint that is neither in
  `PUBLIC_ENDPOINTS` nor carrying `_perms`. `tests/test_route_coverage.py` enforces it.
- **Pricing is a flag, not only a role:** `user.is_pricing` grants the pricing permissions
  on top of whatever the role gives (`rbac.apply_pricing_flag`).

Tables: `department`, `rbac_role`, `permission`, `role_permission`;
`user.department_id / rbac_role_id / manager_id / is_pricing`.
The old `role` table is retired as `role_legacy` and read by nothing.

## Targets and teams

`targets.py` is the pure half (quarters, the split rules, the tree), `sales_target`
the storage, `/targets` the page. Sales only, for now.

- **A target is one amount, one person, one quarter** (`'2026-Q3'`). Set by that
  person's manager. There is no parent column: the parent of a target is the
  target of `user.manager_id` for the same period, so a transfer needs no fixup.
- **Two invariants**, both in `targets.validate_assignment`: children may not
  outgrow the parent (a remainder may be left unassigned, and the split is never
  forced even), and a target may not be cut below what its owner already handed
  down. The top of the tree has no target, so the CEO's first assignment is free.
- **Reading follows scope** — `target.view` is `own` / `team` / `department` down
  the sales ladder, so the existing machinery does the visibility work.
  **Writing is narrower than scope**: only the person's own manager may set their
  number, checked in the route, not by scope.
- **A team is a named branch, never a membership list.** `team.leader_id` names it;
  the members are whoever reports to that leader. `user.team_id` is still dead.
- Achievement is `SUM(total_sell)` over `approval_status='approved'`, attributed by
  `created_at` — `sales_added_date` is null on most rows.
- **The quarter is chosen in the assign dialog**, not inherited from the page, and
  the amount is cleared when it changes: carrying a number across quarters is how
  you set the wrong one without noticing.
- **Amounts are typed with separators and stored without them.** The input groups
  digits, `targets.to_amount` strips the commas. Never parse money in the template.
- `/api/targets/year` is the same tree run once per quarter, so a year column can
  never disagree with the quarter page. `/sales_request` carries a read-only strip
  fed by `/api/targets`, so it is scoped by the same permission with no new gate.

## Costing by assignment

`costing.py` is the pure half (who may assign to whom, the two state machines),
four tables carry it, `/costing` is the page. **Nobody below the Operations Head
types a cost any more.**

- Head → team leaders → members, **each step assigns to its own direct reports**
  and may pick several people at once. One row per person per item in
  `costing_assignment`; there is no "assigned to" column on the item.
- A person may put up **as many proposals as they like** (`costing_proposal`,
  amount + notes + files in `costing_proposal_file`). The **leader who assigned
  them** accepts one; the Head can decide anywhere so an absent leader cannot
  stall an item.
- **Accepting writes the cost.** `sales_request_items.cost_per_item` and
  `total_cost`, every other live proposal on that item is rejected in the same
  transaction, the assignments close, and it lands in the item's own change log
  as well as `costing_log`.
- **`sales_item.cost` now means *see* cost** (columns, totals, operations pages —
  held right down the ladder). Typing one in is `sales_item.cost_direct`, held by
  the Operations Head and admin only.
- **`item_total_cost()` is the only place the total-cost formula lives**
  (cost × qty × days × dimensions). Both ways a cost can arrive go through it, so
  a rental item cannot end up with two different totals. A test asserts they agree.
- Visibility before a decision: author, the leader who asked, and the Head.
  Accepted proposals are visible to anyone who can see the item.
- Every step writes to `costing_log`, including withdrawals and the automatic
  rejections. Nothing cascades out of that table.
- **The Head hands over a request, not an item.** `/api/costing/assign-request`
  fans one request out to a row per item, so the leader receives the lot and
  splits it with the per-item route. Items that already carry a cost are left
  alone unless `include_costed` says otherwise.
- **`/operation_request` shows you your own work.** The list is scoped on the
  viewer's `costing.view`: `all` sees the board, `team` and `own` see only
  requests holding an item assigned to them or handed down by them, and the
  counts and total on those rows cover their items alone. Roles outside the
  costing ladder (the design portals) are not scoped -- the page was never
  about assignments for them.
- **A whole request goes to a team leader only.** `/api/costing/team?leaders=1`
  filters to `rbac.LEVEL_TEAM_LEADER`; the whole-request dialog uses it, so the
  Head cannot skip a rung and take the per-item split away from the leader
  whose job it is. Both forms of the list now skip inactive accounts.
- **The cost modal assigns in bulk.** `/api/costing/assign` takes `item_ids`
  (or the old single `item_id`), and a bad id in the list assigns none of them.
  The modal has a sticky toolbar -- counts, filters (not costed / unassigned /
  on my desk) and a select-all -- so eleven items are one dialog and one round
  trip rather than eleven of each. An untouched item no longer prints
  "not assigned" and "No proposals yet" as two lines of nothing.
- **An alternative option** is a picture plus a comment on `item_images`
  (`is_alternative`), offered by costing as a second way to do an item. It is
  excluded from `attachments` everywhere it is read, so it can never be
  mistaken for what sales specified.

## Department portals

Marketing, Account Management, 2D and 3D Design have a page of their own at
`/marketing`, `/account`, `/design-2d`, `/design-3d`. They are **deliberately
blank** — one shared `templates/portal_placeholder.html`, four thin routes. Filling
one in means changing its `render_template` call, not unpicking a copy.

- Each is gated on `portal.<team>`, granted **by department** in a loop over `ROLES`
  after `SEED_MATRIX`, so a role added to a department later gets its portal by
  being in it. The home page cards read the same permissions.
- Before this they were `link: '#'` and borrowed the nearest-looking permission:
  Marketing on `client.view` (most of the company held it), Account Management on
  `client.edit` and both design portals on `catalog.edit` (their own members did
  not hold either). `tests/test_portals.py` pins that down.

## Numbers and people, on every page

Two things were being done differently on every page, and both are now done in
one place.

- **`static/js/bg-numbers.js`**, loaded by `main.html`, is the only copy.
  `bgNumber(v, places)` and `bgMoney(v)` for reading; `bgGroupDigits` and
  `bgPlainNumber` for typing. An amount field carries `class="bg-amount"` and
  is grouped as it is typed by a delegated handler, so a field rendered into a
  modal later needs no wiring.
- **Grouping is for reading, never for sending.** `float("1,250")` raises and
  `parseFloat("1,250")` is 1, so every reader of a `bg-amount` field goes
  through `bgPlainNumber()` first, hidden fields that get posted stay plain,
  and the shared submit handler strips separators on the way past.
  `tests/test_numbers.py` pins both halves and fails if a grouped field is read
  raw. A `type="number"` input cannot hold a comma -- marking one switches it
  to text, which also drops its `step`/`min`, so the route must validate.
- **"Created by" holds whatever the route that wrote it happened to store**: a
  mobile (`sales_request.created_by`), a display name (`client.added_by`,
  `sales_request_change_log.action_by`), a login name (`user.added_by`) or an
  id (`party_request.requested_by`). `people_index(cur)` + `person_of()`
  resolve any of those to the person; `stamp_person()` adds `_name`,
  `_user_id` and `_mobile` beside the column without touching what is stored.
  Lists show the name with the mobile under it (`.bg-person`).

## The costing loop tells people

Every hand-off notifies, with a link to the request: a proposal tells the leader
who asked (worded as a re-submission when it follows a decision), a decision
tells its author and carries the reason, and an acceptance also tells whoever
lost. `tests/test_costing.py::CostingNotificationTest` captures the calls.

## Comments on a request

- **`/api/mention-users`** is the directory for tagging: gated on
  `sales_request.comment`, active accounts only, name/role/department and
  nothing else. `/api/users` is the admin account list (`user.view`) and must
  not be used for this -- doing so is why `@` did nothing for everyone but
  admins.
- **A comment notifies the request's people**, via `sales_request_audience()`:
  the owner, the costing assignees and whoever assigned them, and anyone
  already in the thread, minus the author and minus anyone separately
  mentioned. There is **no `notifications` table** -- notifications go through
  `notify_users()` into Mongo.

## A costed item is finished

- **`item_lock_reason(row)`** is the only definition: **priced** (a sell price
  is set), then **costed** (a cost is set), then **with the client** (approved
  or in negotiation). The edit route and the edit form both read it.
- The name, quantity, unit, sell type, rental days and dimensions are what the
  cost was worked out from, so they are what is locked (`COSTED_ITEM_FIELDS`).
- **Refusing must be visible.** `update-with-template` edits the items that are
  still open, leaves locked rows untouched, and returns `locked_items` and
  `refused_changes` naming each item, its reason and the fields the edit tried
  to change. It used to skip every item on the request and answer "updated
  successfully".
- The edit form marks locked rows read-only with the reason on them.
- **`/api/sales/requests/edit/<id>` still has none of this** and deletes items
  before re-inserting them without their costs. Nothing in the UI calls it, but
  it is reachable.

## Traps that have already bitten

- **`abort(404)` inside a handler with a blanket `except Exception`** becomes a 500.
  Re-raise `HTTPException` first.
- **DDL commits.** `ALTER TABLE` forces an implicit commit in MySQL, so a `--dry-run`
  that contains one is not dry. Keep DDL outside the transaction.
- **Trigger `update_request_approval_stats_after_item_update`** writes to `sales_request`,
  so `UPDATE sales_request_items ... JOIN sales_request` fails with error 1442.
  Copy the mapping to a temp table first.
- **Class-name collisions.** The `sb-admin-2` theme already defines `.chart-bar`
  (`height: 10rem`) and other generic names. Check new CSS class names against the
  loaded stylesheets before using them.
- **Bootstrap 4 does not stack modals.** Opening one from inside another leaves
  the second backdrop above the second dialog, and closing it strips
  `modal-open` off `<body>` so the page behind takes the scroll. Both are
  handled once in `operation_request.html`; any page that stacks modals needs
  the same two handlers. **Raise only the backdrop of the modal being opened**
  (`$('.modal-backdrop').last()`): raising a set of them takes the lower
  modal's own backdrop up with it, leaving that modal drawn, dimmed and dead to
  every click -- which reads as the page having hung. `focus()` still works
  through an overlay, so verify with `document.elementFromPoint()` or a real
  click, never with focus. `tests/test_template_javascript.py` pins the rule.
- **A page narrowed by `?request=N` must say so.** Notifications deep-link to
  `/operation_request` and `/pricing` with it, which filters the table to one
  row; with the modal closed that is indistinguishable from a table that has
  lost its data. Both pages carry a notice and a **Show all requests** button
  that clears the search and the query parameter.
- **A notification with no link is half a notification.** `notify_users(...,
  link=...)` carries the destination; `notifLink()` in `main.html` guesses one
  from the words for everything already in the tray. Order matters there --
  "costing completed, ready for pricing" belongs to Pricing.
- **Inline template JavaScript must parse.** A broken script block leaves a page that
  returns 200, renders, and does nothing. `tests/test_template_javascript.py` runs
  `node --check` over every template's inline scripts.
- **`$.when` rejects wholesale.** One 403 among parallel fetches blanks a whole page for
  a lower-privileged viewer. Let each fetch resolve either way.
- **Never print the org chart from the browser.** It produced an unreadable chart every
  time. `org_chart_pdf.py` draws it with ReportLab; `/api/org-chart/pdf` serves it.
- **A 200 is not proof.** Check the page rendered its own content, and screenshot or
  render visual work before claiming it is right.

## Tools in the repo

| Script | Purpose |
|---|---|
| `seed_rbac.py` | Rebuild departments, roles, permissions and grants from `rbac.py` |
| `seed_hierarchy.py` | Create a reporting tree from `SPEC`; skips people who already exist |
| `scripts_create_role_accounts.py` | One throwaway account per role (`--delete` to clean up) |
| `scripts_role_access_matrix.py --json out.json` | Probe every GET route as every role |
| `scripts_build_access_report.py matrix.json out.html` | Render that into a report page |
| `org_chart_pdf.py` | Draw the org chart PDF |
| `migrate_users.py`, `backfill_interim_roles.py` | One-off migrations, already applied |

**"Other" is a control, not a value.** `resolve_supplier_type()` stores the
word the user typed as the supplier's type; `/api/suppliers/types` offers the
built-in list plus every type in use, so one typed once is offered thereafter.
A dropdown whose "Other" ends up in the database makes every such row
indistinguishable.

**A connection is closed with the request, not by the handler.**
`connection()` registers each one against `g` and `close_open_connections`
(a `teardown_request`) closes whatever is left. 228 routes returned from an
`except` without closing, and enough of those exhausts MySQL's 151 connections
and hangs every page on the site.

**Say which thing you did.** Deleting an inventory item that has movements
retires it (`discontinued`) rather than removing it; the route returns
`outcome` so the page can say "retired", not "deleted". `get_inventory_items`
honours `status`, where `all` means every live item -- a retired one is found
by asking for it.

**A JSON read is never cacheable.** `no_stale_api_reads` marks every `/api/`
GET `no-store`. Without it the browser answers a post-write table reload out of
its own cache, so a just-deleted row comes back and the next reload drops it --
a page that looks like it is flickering between two versions of the truth.

**Do not offer the request flow to whoever can add the thing outright.**
`party_requests_section.html` hides the "Request a new X" button from holders of
`client.create` / `company.create` / `supplier.create` -- they would be raising
a request for themselves to approve. The card stays: deciding other people's
requests is its other half.

**A button whose route would refuse it is worse than no button.** The entity
page offered Add/Edit/Delete to anyone who could view it; the routes wanted
`entity.create` / `.edit` / `.delete`. Gate the control on the same permission
the route checks. `operations_manager` now holds entity create and edit;
delete stays with admin.

Applied migrations: `rbac_schema_migration.sql`, `owner_backfill_migration.sql`,
`pricing_flag_migration.sql`, `retire_legacy_role_table.sql`, `targets_migration.sql`,
`costing_migration.sql`, `custody_migration.sql`,
`costing_alternatives_migration.sql`, `supplier_email_optional_migration.sql`,
`supplier_type_backfill.sql`.
Backups in `backups/` (gitignored).

`fix_dimension_units.py` has been **run** (8 August 2026): six items rescaled to
metres and their totals rebuilt, including the two `Main Led Screens 3x10` rows
the owner confirmed as 3 x 10 m. It reports `0 to correct, 30 already in metres`
now, so it is a check rather than a pending job.

## Open items

1. **`app.secret_key` is a literal in a public repo** — anyone can forge an admin session
   cookie on the live site. The owner chose to publish as-is; raise it, do not fix unasked.
2. **DB credentials are hardcoded** in `branding_gate.py` and `tests/test_negotiation_routes.py`.
3. **The Assistant role sees every sales request** and can open `/users`, which conflicts
   with "no automatic access to all company data". One line in `rbac.py` if it should change.
4. **All 25 sales requests are owned by user 1**, so `own`/`team`/`department` roles see
   nothing until real work is created. Not a bug.

See `docs/HANDOVER.md` for the full state and history.
