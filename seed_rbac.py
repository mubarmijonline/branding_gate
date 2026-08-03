#!/usr/bin/env python
"""
Seed the RBAC tables from rbac.py.

Idempotent: departments, roles and permissions are upserted by their natural
key, and role_permission is rebuilt from SEED_MATRIX so a removed grant is a
removed row. Re-run it after any edit to rbac.py.

    branding_gate_VENV/bin/python seed_rbac.py            # seed branding_gate
    branding_gate_VENV/bin/python seed_rbac.py --db NAME  # seed another schema
    branding_gate_VENV/bin/python seed_rbac.py --dry-run  # report, change nothing

The final step assigns the admin role to the recovery account (user 1). Until
that row exists, user 1's admin comes only from a team_flag=1 row in the legacy
`role` table, which the cutover stops reading.
"""

import argparse
import sys

import MySQLdb
import MySQLdb.cursors

import rbac

RECOVERY_USER_ID = 1


def connect(db_name):
    return MySQLdb.connect(
        host="localhost",
        user="ps",
        passwd="Aa@123456",
        db=db_name,
        port=3306,
        charset='utf8mb4',
        use_unicode=True,
        cursorclass=MySQLdb.cursors.DictCursor,
    )


def seed_departments(cur):
    for code, name in rbac.DEPARTMENTS.items():
        cur.execute(
            "INSERT INTO department (code, name) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE name = VALUES(name)",
            (code, name),
        )
    cur.execute("SELECT id, code FROM department")
    return {row['code']: row['id'] for row in cur.fetchall()}


def seed_roles(cur, department_ids):
    for code, (name, dept_code, level) in rbac.ROLES.items():
        cur.execute(
            "INSERT INTO rbac_role (code, name, department_id, level) VALUES (%s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE name = VALUES(name), "
            "department_id = VALUES(department_id), level = VALUES(level)",
            (code, name, department_ids.get(dept_code), level),
        )
    cur.execute("SELECT id, code FROM rbac_role")
    return {row['code']: row['id'] for row in cur.fetchall()}


def seed_permissions(cur):
    for code, description in rbac.PERMISSIONS.items():
        cur.execute(
            "INSERT INTO permission (code, description) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE description = VALUES(description)",
            (code, description),
        )
    # Drop vocabulary that no longer exists; the FK cascades to role_permission.
    cur.execute("SELECT code FROM permission")
    stale = [row['code'] for row in cur.fetchall() if row['code'] not in rbac.PERMISSIONS]
    for code in stale:
        cur.execute("DELETE FROM permission WHERE code = %s", (code,))
    return stale


def seed_grants(cur, role_ids):
    """Rebuild role_permission from SEED_MATRIX so removals propagate."""
    rows = rbac.seed_rows()
    cur.execute("DELETE FROM role_permission")
    for role_code, permission_code, scope in rows:
        cur.execute(
            "INSERT INTO role_permission (role_id, permission_code, scope) VALUES (%s, %s, %s)",
            (role_ids[role_code], permission_code, scope),
        )
    return len(rows)


def assign_recovery_admin(cur, department_ids, role_ids):
    """
    Give user 1 the admin role outright. Without this the only surviving
    account loses access the moment team-derived roles stop being read.
    """
    cur.execute("SELECT id, name, rbac_role_id FROM user WHERE id = %s", (RECOVERY_USER_ID,))
    user = cur.fetchone()
    if not user:
        return None
    cur.execute(
        "UPDATE user SET rbac_role_id = %s, department_id = %s WHERE id = %s",
        (role_ids['admin'], department_ids['executive'], RECOVERY_USER_ID),
    )
    return user['name']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='branding_gate')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    # Fail before touching the database if the matrix is inconsistent.
    grant_rows = rbac.seed_rows()

    conn = connect(args.db)
    cur = conn.cursor()
    try:
        department_ids = seed_departments(cur)
        role_ids = seed_roles(cur, department_ids)
        stale = seed_permissions(cur)
        grant_count = seed_grants(cur, role_ids)
        admin_name = assign_recovery_admin(cur, department_ids, role_ids)

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

    print("database:    %s%s" % (args.db, "  (dry run, rolled back)" if args.dry_run else ""))
    print("departments: %d" % len(department_ids))
    print("roles:       %d" % len(role_ids))
    print("permissions: %d%s" % (len(rbac.PERMISSIONS),
                                 "  (%d stale removed)" % len(stale) if stale else ""))
    print("grants:      %d" % grant_count)
    if admin_name:
        print("recovery:    user %d (%s) assigned the admin role" % (RECOVERY_USER_ID, admin_name))
    else:
        print("recovery:    user %d not found, admin NOT assigned" % RECOVERY_USER_ID)
        return 1
    assert grant_count == len(grant_rows)
    return 0


if __name__ == '__main__':
    sys.exit(main())
