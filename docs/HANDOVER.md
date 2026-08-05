# Handover — RBAC revamp

State of the work as of 4 August 2026. `CLAUDE.md` in the repo root carries the
day-to-day rules; this is the fuller picture: what was done, why, and what is left.

## What the system was

One Flask file with a single authorization primitive, `role_required(*names)`:
endpoint-granular, always allowing `admin`, re-querying MySQL on every request.
Alongside it:

- **74 of 252 routes had no gate at all**, including `/api/users/add`, `/edit` and
  `/delete` — any logged-in employee could grant themselves admin.
- `/api/users` returned every user's **plaintext password** in JSON, and the users
  page rendered it in a visible column. Login compared passwords in plain text.
- Role names were free text in `role(role_name, user_id, team_flag)`; when
  `team_flag=1`, `user_id` secretly held a `team_id`. Four roles existed that no code
  read; two the code gated on were assigned to nobody.
- No departments, no manager relation, no row-level scoping. Sales-side list endpoints
  had no `WHERE` clause — every salesperson saw every request.
- Record ownership was stored three incompatible ways: a username on `sales_request`,
  a display name on `finance_transactions`, an int FK on `expense_tracking`.

## What it is now

Eight phases, each its own commit, each deployed before the next.

| Phase | Outcome |
|---|---|
| 1 | Passwords hashed (scrypt, self-migrating on login), credential leak closed, 10 open admin endpoints gated |
| 2 | `department`, `rbac_role`, `permission`, `role_permission` + ownership columns |
| 3 | `rbac.py`: 77 permissions, 21 roles, the grant matrix, and the request-scoped wrappers |
| 4 | Department → Role → Manager admin UI |
| 5 | All routes moved to `@perm`; 0 ungated |
| 6 | Row-level scope enforced in queries; default-deny backstop armed |
| 7 | Legacy role system deleted (461 lines), `role` → `role_legacy` |
| 8 | Users 2–10 deleted, everything they owned repointed to user 1 |

Then: the pricing flag, a rebuilt People page, the seeded organisation, and the
server-drawn org chart PDF.

## The organisation

38 people. One root.

```
Ahmed DiaB (Admin / CEO, 01024527770)
├─ Sales Head → 2 Team Leaders → 4 Members
├─ Assistant
├─ Marketing Manager → 2 Members
├─ Finance Manager → 2 Members
├─ Account Director → 2 Team Leaders → 4 Members
├─ 2D Designer Head → 2 Designers
├─ 3D Head → 2 Designers
├─ Operations Manager → 2 Team Leaders → 4 Members
└─ Pricing Manager → 2 Specialists
```

All 37 seeded people are **placeholders to be renamed** to real staff from the People
page; the position, reporting line and scope stay put when you rename them. Their
mobiles run `01500000001`–`01500000037`; the passwords printed at seeding are in
`backups/seeded_credentials.txt` (gitignored — the repo is public).

User 1's password is hashed and unknown to anyone but the owner.

## Verification already done

- **88 unittest tests**, including the four policy decisions asserted as tests so a
  later edit to the matrix fails the build.
- **Access sweep**: every GET route probed as every role — `scripts_role_access_matrix.py`.
  Latest run: no broken endpoints, no unexpected refusals.
- **Real browser logins as all 37 accounts**, 370 page loads: zero empty pages, zero
  server errors, zero JavaScript errors, and the blocked/open pattern matches the matrix.
- **Scope ladder demonstrated live**: with six requests temporarily reassigned, a Member
  saw their own 2, a Team Leader saw their team's 4, the Sales Head saw the department's
  6, and a Marketing Manager in another department saw 0.

Report page: https://claude.ai/code/artifact/c5dad643-a4f7-46a2-980f-45a212772bb7

## Bugs found and fixed along the way

Most were pre-existing and only surfaced because something actually exercised them.

- Four endpoints returned 500 on every request: the supplier-report Excel export copied
  its session into an inner request context *after* entering it; two catalog endpoints
  queried columns that never shipped; client detail joined a `parent_company` table that
  does not exist.
- A missing file reported as a server error, because `abort(404)` was swallowed by the
  handler's own `except Exception`.
- The sales request page rendered an **empty shell** for every non-admin role — its gate
  still tested legacy role names. Eighteen further card gates had the same fault.
- The pricing controls were hidden from Pricing itself, same cause.
- The users page was **inert in the browser**: a regex cleanup had deleted the opening
  line of a multi-line handler and left its closing brace.
- The People page went blank for any non-admin viewer, because `$.when` rejects wholesale.
- The sign-in logo was stretched and clipped by `width:115%; height:90%`.
- `main.html` loaded two SweetAlert bundles.

## Judgement calls worth knowing

- **The grant matrix lives in code, not the UI.** `rbac.py` → `seed_rbac.py`. A change is
  a reviewable diff, not an invisible UPDATE. The Roles tab is deliberately read-only.
- **One role per user.** `user.rbac_role_id` is scalar. An exception should be a new role,
  not a new mechanism. Pricing is the single cross-cutting flag.
- **Teams were retired**, not repurposed: they granted nothing once permissions landed,
  and department + reporting line replaces them. Table and column left in place.
- **`/api/finance/my-balance` keeps its hardcoded session filter.** "My balance" should
  mean mine; letting a manager's team scope widen it would be the wrong reading.
- **Legacy columns kept for reference** — `sales_request.created_by`, `client.added_by`,
  `team.department_name`. Nothing reads them any more; drop them a quarter later.

## Open items

1. **`app.secret_key` is the literal `"branding gate api secret key"`** in a public repo.
   Anyone who reads it can forge a session cookie for `user_id: 1` on the live site. The
   owner was told and chose to publish as-is. Two-minute fix when they want it.
2. **DB credentials hardcoded** in `branding_gate.py:53` and
   `tests/test_negotiation_routes.py`. MySQL is bound to localhost and the `ps` user is
   `localhost`-only, so it is not remotely usable — but it is in a public repo.
3. **The Assistant sees every sales request** and can open `/users`. The brief said the
   Assistant should have no automatic access to all company data. One line in `rbac.py`.
4. **All 25 sales requests belong to user 1** after the phase 8 migration, so
   `own`/`team`/`department` roles see nothing yet. Resolves itself as work is created.
5. **Scratch databases** `bg_restore_test` and `bg_migrate_test` may still exist from
   migration rehearsals. Safe to drop.

## Deferred by design

Per-user permission overrides · multiple roles per user · a permission audit log ·
per-record ACLs · numeric approval ceilings for `pricing_specialist` ("within approved
limits" needs a number from the business) · editing the matrix from the UI ·
dropping the legacy text columns · CSRF, rate limiting, secure cookie flags ·
splitting the 22k-line file into blueprints.
