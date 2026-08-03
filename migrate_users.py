#!/usr/bin/env python
"""
RBAC revamp, phase 8: reduce the user base to the recovery account.

Deletes users 2-10 and repoints everything they owned onto user 1
(01024527770). The organisation is then rebuilt through the users page.

Irreversible. Take a dump first; --dry-run rolls back so the plan can be
inspected against a restored copy.

    branding_gate_VENV/bin/python migrate_users.py --db bg_migrate_test --dry-run
    branding_gate_VENV/bin/python migrate_users.py --db bg_migrate_test
    branding_gate_VENV/bin/python migrate_users.py            # production

Two tables carry a unique index across the column being repointed, so a
blind UPDATE would raise a duplicate-key error:

  user_finance_balances   UNIQUE (user_id)
  sales_request_comment_mentions  UNIQUE (comment_id, mentioned_user_id)

Rows that would collide are deleted rather than merged: a balance row is a
per-user aggregate that means nothing once reassigned, and a duplicate
mention is simply the same person mentioned twice.
"""

import argparse
import sys

import MySQLdb
import MySQLdb.cursors

KEEP_USER_ID = 1
DELETE_RANGE = (2, 10)

# (table, column) pairs holding a user id, discovered from information_schema
# and confirmed to contain ids in the delete range.
REPOINT = [
    ('approved_item_components',       'created_by'),
    ('approved_item_components',       'received_by'),
    ('client',                         'owner_user_id'),
    ('company_documents',              'uploaded_by'),
    ('expense_tracking',               'user_id'),
    ('expense_tracking',               'manager_approved_by_user_id'),
    ('expense_tracking',               'finance_approved_by_user_id'),
    ('expense_tracking',               'rejected_by_user_id'),
    ('finance_approval_log',           'action_by_user_id'),
    ('finance_transactions',           'added_by_user_id'),
    ('finance_transactions',           'approved_by_user_id'),
    ('finance_transactions',           'rejected_by_user_id'),
    ('item_client_approval_log',       'action_by'),
    ('item_images',                    'uploaded_by'),
    ('negotiation_logs',               'actor_user_id'),
    ('negotiation_requests',           'sales_head_user_id'),
    ('request_attachment',             'uploaded_by'),
    ('sales_request',                  'owner_user_id'),
    ('sales_request_comments',         'user_id'),
    ('sales_request_comments',         'deleted_by'),
    ('sales_request_files',            'uploaded_by'),
    ('sales_request_items',            'submitted_by'),
    ('sales_request_items',            'supplier_received_by'),
    ('user_balance_history',           'user_id'),
    ('user_balance_history',           'created_by'),
    ('user_balance_transfers',         'from_user_id'),
    ('user_balance_transfers',         'to_user_id'),
    ('user_balance_transfers',         'requested_by'),
    ('user_balance_transfers',         'approved_by'),
    ('user_expense_tracking',          'user_id'),
    ('user_expense_tracking',          'approved_by'),
    ('user_loans',                     'user_id'),
    ('user_loan_transactions',         'user_id'),
    ('user_loan_transactions',         'created_by_user_id'),
]

# Rows that cannot be repointed because of a unique index. Each entry is
# (table, column, sql deleting only the rows that would collide).
COLLISIONS = [
    (
        'user_finance_balances', 'user_id',
        "DELETE FROM user_finance_balances WHERE user_id BETWEEN %s AND %s",
    ),
    (
        # An @-mention of someone who no longer exists cannot be reassigned:
        # repointing it would fabricate a mention of the recovery account that
        # never happened. The foreign key cascades anyway, so delete it here
        # where it is visible in the report rather than letting it vanish
        # silently with the user row. The comment text itself is repointed and
        # survives.
        'sales_request_comment_mentions', 'mentioned_user_id',
        "DELETE FROM sales_request_comment_mentions WHERE mentioned_user_id BETWEEN %s AND %s",
    ),
]


def connect(db_name):
    return MySQLdb.connect(
        host="localhost", user="ps", passwd="Aa@123456", db=db_name,
        port=3306, charset='utf8mb4', use_unicode=True,
        cursorclass=MySQLdb.cursors.DictCursor,
    )


def column_exists(cur, table, column):
    cur.execute("""
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s
    """, (table, column))
    return cur.fetchone() is not None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='branding_gate')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    low, high = DELETE_RANGE
    conn = connect(args.db)
    cur = conn.cursor()
    report = []
    try:
        cur.execute("SELECT id, name, username FROM user WHERE id = %s", (KEEP_USER_ID,))
        keeper = cur.fetchone()
        if not keeper:
            print("Recovery account %d not found; refusing to run." % KEEP_USER_ID)
            return 1

        cur.execute("""
            SELECT u.id, u.name, r.code AS role_code FROM user u
            LEFT JOIN rbac_role r ON r.id = u.rbac_role_id
            WHERE u.id BETWEEN %s AND %s ORDER BY u.id
        """, (low, high))
        doomed = cur.fetchall()

        # The keeper must hold a role, or the surviving account cannot log in
        # to anything after the other users are gone.
        cur.execute("""
            SELECT r.code FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
            WHERE u.id = %s
        """, (KEEP_USER_ID,))
        keeper_role = cur.fetchone()
        if not keeper_role:
            print("Recovery account has no rbac_role; refusing to run.")
            return 1

        # 1. Drop rows that a unique index would make un-repointable.
        for table, column, sql in COLLISIONS:
            if not column_exists(cur, table, column):
                continue
            params = (low, high) if sql.count('%s') == 2 else (low, high, KEEP_USER_ID)
            cur.execute(sql, params)
            if cur.rowcount:
                report.append(("deleted (unique index)", '%s.%s' % (table, column), cur.rowcount))

        # 2. Repoint everything else onto the recovery account.
        for table, column in REPOINT:
            if not column_exists(cur, table, column):
                continue
            cur.execute(
                "UPDATE `%s` SET `%s` = %%s WHERE `%s` BETWEEN %%s AND %%s" % (table, column, column),
                (KEEP_USER_ID, low, high),
            )
            if cur.rowcount:
                report.append(("repointed", '%s.%s' % (table, column), cur.rowcount))

        # 3. Nobody may still report to a user about to disappear.
        cur.execute("UPDATE user SET manager_id = NULL WHERE manager_id BETWEEN %s AND %s", (low, high))
        if cur.rowcount:
            report.append(("cleared", 'user.manager_id', cur.rowcount))

        # 4. Historical role rows for the departing users.
        cur.execute("DELETE FROM role_legacy WHERE user_id BETWEEN %s AND %s AND team_flag = 0", (low, high))
        if cur.rowcount:
            report.append(("deleted", 'role_legacy (direct)', cur.rowcount))

        # 5. The users themselves.
        cur.execute("DELETE FROM user WHERE id BETWEEN %s AND %s", (low, high))
        deleted_users = cur.rowcount
        report.append(("deleted", 'user', deleted_users))

        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
            # Stop a future user inheriting a departed id. This is DDL, which
            # forces an implicit commit in MySQL, so it must run *after* the
            # transaction rather than inside it -- otherwise --dry-run silently
            # commits everything that came before it.
            cur.execute("ALTER TABLE user AUTO_INCREMENT = 100")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    print("database: %s%s" % (args.db, "  (dry run, rolled back)" if args.dry_run else ""))
    print("keeping:  user %d - %s (%s), role %s"
          % (keeper['id'], keeper['name'], keeper['username'], keeper_role['code']))
    print("removing: %s" % ", ".join('%d %s' % (u['id'], u['name']) for u in doomed))
    print()
    for action, target, count in report:
        print("  %-24s %-40s %4d" % (action, target, count))
    print()
    print("users deleted: %d" % deleted_users)
    return 0


if __name__ == '__main__':
    sys.exit(main())
