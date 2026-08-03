#!/usr/bin/env python
"""
Create a reporting tree through the real /api/users/add endpoint, so the same
validation runs as for a human admin.

Edit SPEC and re-run to build a different structure. Accounts are created
top-down because a manager must exist before their report. Passwords are
random and printed once -- they are stored hashed and cannot be read back.

    branding_gate_VENV/bin/python seed_hierarchy.py
    branding_gate_VENV/bin/python seed_hierarchy.py --dry-run
"""

import argparse
import secrets
import string
import sys

import branding_gate as bg

ADMIN_USER_ID = 1

# (key, display name, role code, manager key or None for the CEO)
SPEC = [
    ('head',      'Sales Head',           'sales_head',        None),
    ('leader1',   'Sales Team Leader 1',  'sales_team_leader', 'head'),
    ('leader2',   'Sales Team Leader 2',  'sales_team_leader', 'head'),
    ('member1',   'Sales Member 1',       'sales_member',      'leader1'),
    ('member2',   'Sales Member 2',       'sales_member',      'leader1'),
    ('member3',   'Sales Member 3',       'sales_member',      'leader2'),
    ('member4',   'Sales Member 4',       'sales_member',      'leader2'),
]

MOBILE_PREFIX = '0150000'   # + a 4-digit sequence
EMAIL_DOMAIN = 'branding-gate.com'


def random_password():
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(12))


def admin_client():
    perms, role_code = bg.load_permissions(ADMIN_USER_ID)
    client = bg.app.test_client()
    with client.session_transaction() as flask_session:
        flask_session.update({
            'user_id': ADMIN_USER_ID, 'mobile': '01024527770',
            'email': 'ahmeddiab1712@gmail.com', 'username': 'a.diab',
            'name': 'Ahmed DiaB', 'roles': [role_code],
            'perms': perms, 'role_code': role_code,
        })
    return client


def lookup(cur, table, code):
    cur.execute("SELECT id FROM %s WHERE code = %%s" % table, (code,))
    row = cur.fetchone()
    return row['id'] if row else None


def next_free_mobile(cur, index):
    while True:
        mobile = '%s%04d' % (MOBILE_PREFIX, index)
        cur.execute("SELECT id FROM user WHERE mobile = %s", (mobile,))
        if not cur.fetchone():
            return mobile, index
        index += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    conn, cur = bg.connection()
    department_id = lookup(cur, 'department', 'sales')
    role_ids = {}
    for _key, _name, role_code, _mgr in SPEC:
        role_ids[role_code] = lookup(cur, 'rbac_role', role_code)
    cur.close()
    conn.close()

    missing = [code for code, rid in role_ids.items() if not rid]
    if not department_id or missing:
        print("missing department 'sales' or roles: %s" % missing)
        return 1

    if args.dry_run:
        print("would create %d accounts under user %d:" % (len(SPEC), ADMIN_USER_ID))
        for key, name, role_code, manager_key in SPEC:
            print("  %-22s %-20s reports to %s"
                  % (name, role_code, manager_key or 'Admin / CEO'))
        return 0

    client = admin_client()
    created = {}
    credentials = []
    index = 1

    for key, name, role_code, manager_key in SPEC:
        conn, cur = bg.connection()
        mobile, index = next_free_mobile(cur, index)
        cur.close()
        conn.close()
        index += 1

        manager_id = created[manager_key] if manager_key else ADMIN_USER_ID
        password = random_password()
        username = name.lower().replace(' ', '.')

        response = client.post('/api/users/add', json={
            'name': name,
            'username': username,
            'title': name,
            'mobile': mobile,
            'email': '%s@%s' % (username, EMAIL_DOMAIN),
            'password': password,
            'department_id': department_id,
            'rbac_role_id': role_ids[role_code],
            'manager_id': manager_id,
        })
        body = response.get_json() or {}
        if not body.get('success'):
            print("  FAILED %-22s %s" % (name, body.get('error')))
            continue

        conn, cur = bg.connection()
        cur.execute("SELECT id FROM user WHERE username = %s", (username,))
        new_id = cur.fetchone()['id']
        cur.close()
        conn.close()

        created[key] = new_id
        credentials.append((name, new_id, mobile, username, password, manager_id))
        print("  created %-22s id=%-4s reports to %s" % (name, new_id, manager_id))

    print()
    print("%-22s %-5s %-13s %-24s %-14s %s"
          % ('name', 'id', 'mobile (login)', 'username', 'password', 'reports to'))
    print('-' * 100)
    for name, uid, mobile, username, password, manager_id in credentials:
        print("%-22s %-5s %-13s %-24s %-14s %s"
              % (name, uid, mobile, username, password, manager_id))
    print()
    print("Log in with the mobile number and the password. Passwords are stored")
    print("hashed and cannot be read back -- reset them from the users page.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
