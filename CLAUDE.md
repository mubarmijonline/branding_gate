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
  test_negotiation_templates test_negotiation_routes test_sales_request_journey_pdf
```

88 tests. `tests/test_design_system.py` is pytest-style (bare functions) and is run by
calling its `test_*` functions in a loop.

## Access control

Authorization is `rbac.py` (pure policy, no Flask/MySQL) plus wrappers in `branding_gate.py`.

- **77 permissions** as `resource.action`; **21 roles** across 4 levels (0 exec → 3 member);
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
`pricing_flag_migration.sql`, `retire_legacy_role_table.sql`.
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
