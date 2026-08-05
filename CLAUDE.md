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
  test_targets test_portals
```

129 tests. `tests/test_design_system.py` is pytest-style (bare functions) and is run by
calling its `test_*` functions in a loop.

## Access control

Authorization is `rbac.py` (pure policy, no Flask/MySQL) plus wrappers in `branding_gate.py`.

- **84 permissions** as `resource.action`; **21 roles** across 4 levels (0 exec → 3 member);
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

Applied migrations: `rbac_schema_migration.sql`, `owner_backfill_migration.sql`,
`pricing_flag_migration.sql`, `retire_legacy_role_table.sql`, `targets_migration.sql`.
Backups in `backups/` (gitignored).

## Open items

1. **`app.secret_key` is a literal in a public repo** — anyone can forge an admin session
   cookie on the live site. The owner chose to publish as-is; raise it, do not fix unasked.
2. **DB credentials are hardcoded** in `branding_gate.py` and `tests/test_negotiation_routes.py`.
3. **The Assistant role sees every sales request** and can open `/users`, which conflicts
   with "no automatic access to all company data". One line in `rbac.py` if it should change.
4. **All 25 sales requests are owned by user 1**, so `own`/`team`/`department` roles see
   nothing until real work is created. Not a bug.

See `docs/HANDOVER.md` for the full state and history.
