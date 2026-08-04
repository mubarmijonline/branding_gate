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

# (key, display name, role code, department code, manager key or None for the CEO)
#
# Placeholder people for every branch of the org chart. Rename them to the real
# person from the People page; the position stays put. Re-running skips anyone
# whose username already exists, so this is safe to run again after editing.
SPEC = [
    ('assistant',   'Assistant',              'assistant',              'executive',  None),

    ('sales_head',  'Sales Head',             'sales_head',             'sales',      None),
    ('sales_tl1',   'Sales Team Leader 1',    'sales_team_leader',      'sales',      'sales_head'),
    ('sales_tl2',   'Sales Team Leader 2',    'sales_team_leader',      'sales',      'sales_head'),
    ('sales_m1',    'Sales Member 1',         'sales_member',           'sales',      'sales_tl1'),
    ('sales_m2',    'Sales Member 2',         'sales_member',           'sales',      'sales_tl1'),
    ('sales_m3',    'Sales Member 3',         'sales_member',           'sales',      'sales_tl2'),
    ('sales_m4',    'Sales Member 4',         'sales_member',           'sales',      'sales_tl2'),

    ('mkt_mgr',     'Marketing Manager',      'marketing_manager',      'marketing',  None),
    ('mkt_m1',      'Marketing Member 1',     'marketing_member',       'marketing',  'mkt_mgr'),
    ('mkt_m2',      'Marketing Member 2',     'marketing_member',       'marketing',  'mkt_mgr'),

    ('fin_mgr',     'Finance Manager',        'finance_manager',        'finance',    None),
    ('fin_m1',      'Finance Member 1',       'finance_member',         'finance',    'fin_mgr'),
    ('fin_m2',      'Finance Member 2',       'finance_member',         'finance',    'fin_mgr'),

    ('acc_dir',     'Account Director',       'account_director',       'account',    None),
    ('acc_tl1',     'Account Team Leader 1',  'account_team_leader',    'account',    'acc_dir'),
    ('acc_tl2',     'Account Team Leader 2',  'account_team_leader',    'account',    'acc_dir'),
    ('acc_m1',      'Account Member 1',       'account_member',         'account',    'acc_tl1'),
    ('acc_m2',      'Account Member 2',       'account_member',         'account',    'acc_tl1'),
    ('acc_m3',      'Account Member 3',       'account_member',         'account',    'acc_tl2'),
    ('acc_m4',      'Account Member 4',       'account_member',         'account',    'acc_tl2'),

    ('d2d_head',    '2D Designer Head',       'design_2d_head',         'design_2d',  None),
    ('d2d_m1',      '2D Designer 1',          'design_2d_member',       'design_2d',  'd2d_head'),
    ('d2d_m2',      '2D Designer 2',          'design_2d_member',       'design_2d',  'd2d_head'),

    ('d3d_head',    '3D Head',                'design_3d_head',         'design_3d',  None),
    ('d3d_m1',      '3D Designer 1',          'design_3d_member',       'design_3d',  'd3d_head'),
    ('d3d_m2',      '3D Designer 2',          'design_3d_member',       'design_3d',  'd3d_head'),

    ('ops_mgr',     'Operations Manager',     'operations_manager',     'operations', None),
    ('ops_tl1',     'Operations Team Leader 1', 'operations_team_leader', 'operations', 'ops_mgr'),
    ('ops_tl2',     'Operations Team Leader 2', 'operations_team_leader', 'operations', 'ops_mgr'),
    ('ops_m1',      'Operations Member 1',    'operations_member',      'operations', 'ops_tl1'),
    ('ops_m2',      'Operations Member 2',    'operations_member',      'operations', 'ops_tl1'),
    ('ops_m3',      'Operations Member 3',    'operations_member',      'operations', 'ops_tl2'),
    ('ops_m4',      'Operations Member 4',    'operations_member',      'operations', 'ops_tl2'),

    ('prc_mgr',     'Pricing Manager',        'pricing_manager',        'pricing',    None),
    ('prc_s1',      'Pricing Specialist 1',   'pricing_specialist',     'pricing',    'prc_mgr'),
    ('prc_s2',      'Pricing Specialist 2',   'pricing_specialist',     'pricing',    'prc_mgr'),
]

MOBILE_PREFIX = '0150000'   # + a 4-digit sequence
EMAIL_DOMAIN = 'branding-gate.com'


def username_for(name):
    """Stable key for a position, so re-running recognises an existing person
    even after they have been renamed."""
    return name.lower().replace(' ', '.')


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
    department_ids, role_ids = {}, {}
    for _key, _name, role_code, dept_code, _mgr in SPEC:
        role_ids[role_code] = lookup(cur, 'rbac_role', role_code)
        department_ids[dept_code] = lookup(cur, 'department', dept_code)
    cur.execute("SELECT id, username, name FROM user")
    by_username = {row['username']: row for row in cur.fetchall()}
    cur.close()
    conn.close()

    missing_roles = sorted(c for c, i in role_ids.items() if not i)
    missing_depts = sorted(c for c, i in department_ids.items() if not i)
    if missing_roles or missing_depts:
        print("missing roles: %s\nmissing departments: %s" % (missing_roles, missing_depts))
        return 1

    if args.dry_run:
        print("%d positions in the chart" % len(SPEC))
        for key, name, role_code, dept_code, manager_key in SPEC:
            state = 'exists' if username_for(name) in by_username else 'would create'
            print("  %-12s %-26s %-24s %-11s reports to %s"
                  % (state, name, role_code, dept_code, manager_key or 'Admin / CEO'))
        return 0

    client = admin_client()
    created, credentials, skipped = {}, [], []
    index = 1

    for key, name, role_code, dept_code, manager_key in SPEC:
        username = username_for(name)

        # Already placed: remember the id so their reports can point at them,
        # and leave the account alone in case it has been renamed since.
        if username in by_username:
            created[key] = by_username[username]['id']
            skipped.append((name, by_username[username]['name']))
            continue

        conn, cur = bg.connection()
        mobile, index = next_free_mobile(cur, index)
        cur.close()
        conn.close()
        index += 1

        manager_id = created.get(manager_key, ADMIN_USER_ID) if manager_key else ADMIN_USER_ID
        password = random_password()

        response = client.post('/api/users/add', json={
            'name': name,
            'username': username,
            'title': name,
            'mobile': mobile,
            'email': '%s@%s' % (username, EMAIL_DOMAIN),
            'password': password,
            'department_id': department_ids[dept_code],
            'rbac_role_id': role_ids[role_code],
            'manager_id': manager_id,
        })
        payload = response.get_json() or {}
        if not payload.get('success'):
            print("  FAILED %-26s %s" % (name, payload.get('error')))
            continue

        conn, cur = bg.connection()
        cur.execute("SELECT id FROM user WHERE username = %s", (username,))
        new_id = cur.fetchone()['id']
        cur.close()
        conn.close()

        created[key] = new_id
        credentials.append((name, new_id, mobile, username, password, manager_id))
        print("  created %-26s id=%-4s reports to %s" % (name, new_id, manager_id))

    if skipped:
        print()
        print("already in place, left untouched:")
        for spec_name, actual_name in skipped:
            note = '' if spec_name == actual_name else '  (now: %s)' % actual_name
            print("  %s%s" % (spec_name, note))

    if credentials:
        print()
        print("%-26s %-5s %-13s %-26s %-14s %s"
              % ('name', 'id', 'mobile (login)', 'username', 'password', 'manager id'))
        print('-' * 104)
        for name, uid, mobile, username, password, manager_id in credentials:
            print("%-26s %-5s %-13s %-26s %-14s %s"
                  % (name, uid, mobile, username, password, manager_id))
        print()
        print("Sign in with the mobile number. Passwords are stored hashed and")
        print("cannot be read back -- reset them from the People page.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
