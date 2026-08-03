#!/usr/bin/env python
"""
Create one account per RBAC role, wired into a real reporting hierarchy.

Used to verify what each role can actually reach. Accounts go through the
real /api/users/add endpoint so the same validation runs as for a human
admin. Passwords are random and printed once.

    branding_gate_VENV/bin/python scripts_create_role_accounts.py
    branding_gate_VENV/bin/python scripts_create_role_accounts.py --delete

Every account is named with the ROLE_ACCOUNT_PREFIX so cleanup is exact.
"""

import argparse
import secrets
import string
import sys

import MySQLdb
import MySQLdb.cursors

import branding_gate as bg
import rbac

ROLE_ACCOUNT_PREFIX = 'rolecheck.'
MOBILE_BASE = 1990000000  # 01990000001 upward, outside any real range


def random_password():
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(14))


def admin_client():
    perms, role_code = bg.load_permissions(1)
    client = bg.app.test_client()
    with client.session_transaction() as flask_session:
        flask_session.update({
            'user_id': 1, 'mobile': '01024527770', 'email': 'ahmeddiab1712@gmail.com',
            'username': 'a.diab', 'name': 'Ahmed DiaB',
            'roles': [role_code], 'perms': perms, 'role_code': role_code,
        })
    return client


def existing_accounts(cur):
    cur.execute(
        "SELECT id, username, name FROM user WHERE username LIKE %s ORDER BY id",
        (ROLE_ACCOUNT_PREFIX + '%',),
    )
    return cur.fetchall()


def delete_accounts():
    conn, cur = bg.connection()
    rows = existing_accounts(cur)
    for row in rows:
        # Clear any reporting line pointing at this account first.
        cur.execute("UPDATE user SET manager_id = NULL WHERE manager_id = %s", (row['id'],))
    cur.execute("DELETE FROM user WHERE username LIKE %s", (ROLE_ACCOUNT_PREFIX + '%',))
    conn.commit()
    cur.close()
    conn.close()
    print("deleted %d role-check accounts" % len(rows))
    return 0


def create_accounts():
    conn, cur = bg.connection()
    cur.execute("SELECT id, code FROM department")
    departments = {r['code']: r['id'] for r in cur.fetchall()}
    cur.execute("SELECT id, code, level FROM rbac_role")
    roles = {r['code']: r for r in cur.fetchall()}
    cur.close()
    conn.close()

    client = admin_client()
    created = {}
    credentials = []
    seq = 0

    # Level order matters: a manager must exist before their report.
    ordered = sorted(rbac.ROLES.items(), key=lambda kv: (kv[1][2], kv[0]))

    for role_code, (display_name, dept_code, level) in ordered:
        if role_code == 'admin':
            continue  # user 1 already holds it
        seq += 1
        role = roles[role_code]

        # Report to the most senior account already created in this department,
        # falling back to the recovery admin.
        manager_id = 1
        for candidate_code, candidate_id in created.items():
            candidate = rbac.ROLES[candidate_code]
            if candidate[1] == dept_code and candidate[2] < level:
                manager_id = candidate_id

        password = random_password()
        payload = {
            'name': 'Role Check %s' % display_name,
            'username': ROLE_ACCOUNT_PREFIX + role_code,
            'title': display_name,
            'mobile': '0%d' % (MOBILE_BASE + seq),
            'email': '%s@rolecheck.invalid' % role_code,
            'password': password,
            'department_id': departments.get(dept_code),
            'rbac_role_id': role['id'],
            'manager_id': manager_id,
        }
        response = client.post('/api/users/add', json=payload)
        body = response.get_json() or {}
        if not body.get('success'):
            print("  FAILED %-24s %s" % (role_code, body.get('error')))
            continue

        conn, cur = bg.connection()
        cur.execute("SELECT id FROM user WHERE username = %s", (payload['username'],))
        new_id = cur.fetchone()['id']
        cur.close()
        conn.close()

        created[role_code] = new_id
        credentials.append((role_code, new_id, payload['mobile'], password, manager_id))
        print("  created %-24s id=%-4s reports to %s" % (role_code, new_id, manager_id))

    print()
    print("%-24s %-5s %-13s %-16s %s" % ('role', 'id', 'mobile', 'password', 'manager'))
    for role_code, uid, mobile, password, manager_id in credentials:
        print("%-24s %-5s %-13s %-16s %s" % (role_code, uid, mobile, password, manager_id))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delete', action='store_true')
    args = parser.parse_args()
    return delete_accounts() if args.delete else create_accounts()


if __name__ == '__main__':
    sys.exit(main())
