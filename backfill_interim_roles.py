#!/usr/bin/env python
"""
Assign an interim RBAC role to every user who still has none.

The gate cutover replaces role_required with permission checks. A user with no
rbac_role_id resolves to an empty permission set and is therefore denied
everything, so existing accounts need a role before their modules switch over.

The mapping is derived from the legacy `role` rows the user already holds --
direct roles and team-inherited ones alike -- not from job titles, so it
preserves current capability rather than guessing at intent. Where a legacy
role granted unrestricted access, the interim role is the widest equivalent;
scope only starts being enforced in phase 6, by which point the real hierarchy
should be built in the UI.

Interim only. Phase 8 deletes users 2-10 and rebuilds the organisation.

    branding_gate_VENV/bin/python backfill_interim_roles.py --dry-run
    branding_gate_VENV/bin/python backfill_interim_roles.py
    branding_gate_VENV/bin/python backfill_interim_roles.py --db bg_restore_test
"""

import argparse
import sys

import MySQLdb
import MySQLdb.cursors

# Legacy role name -> interim rbac_role code, most senior first. A user holding
# several legacy roles gets the first match in this order.
LEGACY_ROLE_PRIORITY = [
    ('admin',            'admin'),
    ('finance',          'finance_manager'),
    ('pricing',          'pricing_manager'),
    ('operation',        'operations_manager'),
    ('marketing',        'marketing_manager'),
    ('account manager',  'account_director'),
    ('sales',            'sales_head'),
    ('sales operation',  'operations_member'),
    ('2D designer',      'design_2d_member'),
    ('3D graphic',       'design_3d_member'),
]

# Users holding none of the above still need somewhere to sit.
FALLBACK_ROLE = None


def connect(db_name):
    return MySQLdb.connect(
        host="localhost", user="ps", passwd="Aa@123456", db=db_name,
        port=3306, charset='utf8mb4', use_unicode=True,
        cursorclass=MySQLdb.cursors.DictCursor,
    )


def legacy_roles_for(cur, user_id):
    """Direct roles plus roles inherited from the user's team."""
    cur.execute("""
        SELECT role_name FROM role WHERE user_id = %s AND team_flag = 0
        UNION
        SELECT role_name FROM role WHERE user_id = (
            SELECT team_id FROM user WHERE id = %s AND team_id IS NOT NULL
        ) AND team_flag = 1
    """, (user_id, user_id))
    return {row['role_name'] for row in cur.fetchall()}


def pick_role(legacy):
    for legacy_name, rbac_code in LEGACY_ROLE_PRIORITY:
        if legacy_name in legacy:
            return rbac_code
    return FALLBACK_ROLE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='branding_gate')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    conn = connect(args.db)
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, code, department_id FROM rbac_role")
        roles = {row['code']: row for row in cur.fetchall()}

        cur.execute("SELECT id, name, username, title FROM user WHERE rbac_role_id IS NULL ORDER BY id")
        pending = cur.fetchall()

        assigned, skipped = [], []
        for user in pending:
            legacy = legacy_roles_for(cur, user['id'])
            code = pick_role(legacy)
            if not code or code not in roles:
                skipped.append((user, sorted(legacy)))
                continue
            role = roles[code]
            cur.execute(
                "UPDATE user SET rbac_role_id = %s, department_id = COALESCE(department_id, %s) WHERE id = %s",
                (role['id'], role['department_id'], user['id'])
            )
            assigned.append((user, sorted(legacy), code))

        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    print("database: %s%s" % (args.db, "  (dry run, rolled back)" if args.dry_run else ""))
    print("unassigned users found: %d" % len(pending))
    for user, legacy, code in assigned:
        print("  id %-3s %-16s legacy=%-40s -> %s" % (
            user['id'], user['name'][:16], ",".join(legacy) or '(none)', code))
    for user, legacy in skipped:
        print("  id %-3s %-16s legacy=%-40s -> NOT ASSIGNED" % (
            user['id'], user['name'][:16], ",".join(legacy) or '(none)'))
    print("assigned: %d   skipped: %d" % (len(assigned), len(skipped)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
