# 08 - Extra permissions and notification classes

**Goal:** an admin gives any role, department, team or person an extra
permission from the People & Access screen, without a code change or a
reseed; and every notification is either Important (something waits on the
reader) or an Announcement, shown in separate tabs.

**Acceptance:**
- `tests/test_permission_grants.py`: a grant to a person, a role, a
  department and a team each reaches `load_permissions`; the wider scope
  wins; `users_holding` includes grantees; only `role.grant` may add or
  remove; seeding does not remove a grant.
- `tests/test_notification_category.py`: titles classify as expected.
- Live: Gamal given `sales_request.delete` sees the Delete button on a sales
  request; Beshoy's bell shows Important only, Announcements in their own tab.

**Status:** live 2026-10-27. Gamal holds `sales_request.delete` (all) as a person extra; 449 stored notifications classified (325 important, 124 announcements), backup in `private_backups/notification_category_before_20261027.json`.
