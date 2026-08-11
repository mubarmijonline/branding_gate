"""
Factory reset: empty the system, keep the people who log in.

Every sales request, item, costing, negotiation, approval, expense, عهدة,
finance transaction, client, company, supplier and catalog entry goes. What
stays is who works here and what the app needs in order to run at all.

Dry run by default. Nothing is written without --apply.

    python factory_reset.py            # say what would go
    python factory_reset.py --apply    # do it

Kept, and why:

* user, rbac_role, permission, role_permission, department, team, role_legacy
  -- the people and their access. The whole point of the exercise.
* finance_categories, finance_subcategories -- branding_gate.py posts to
  category 16 (internal transfer out) and 44 (internal transfer in) by number.
  Wipe these and the numbers point at nothing, so approving a عهدة or an expense
  would write a transaction into a category that does not exist.
* request_type, template_field_def, request_templates -- the shape of the
  request form itself. Without them there is no form to raise a request with.

Views are skipped: there are no rows in a view to delete.
"""

import sys

import MySQLdb
import MySQLdb.cursors

KEEP = {
    # People and access
    'user', 'rbac_role', 'permission', 'role_permission', 'department',
    'team', 'role_legacy',
    # Configuration the code addresses by id or cannot run without
    'finance_categories', 'finance_subcategories',
    'request_type', 'template_field_def', 'request_templates',
}


def connect():
    return MySQLdb.connect(host='localhost', user='ps', passwd='Aa@123456',
                           db='branding_gate', charset='utf8mb4',
                           cursorclass=MySQLdb.cursors.DictCursor)


def main(apply_it):
    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT table_name AS name, table_type AS kind
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
    """)
    rows = cur.fetchall()
    tables = sorted(r['name'] for r in rows if r['kind'] == 'BASE TABLE')
    views = sorted(r['name'] for r in rows if r['kind'] != 'BASE TABLE')

    to_wipe, kept = [], []
    for name in tables:
        cur.execute("SELECT COUNT(*) AS n FROM `%s`" % name)
        count = cur.fetchone()['n']
        (kept if name in KEEP else to_wipe).append((name, count))

    print("KEEPING %d table(s):" % len(kept))
    for name, count in kept:
        print("  %-34s %6d rows" % (name, count))
    print()
    print("WIPING %d table(s), %d rows:" % (
        len(to_wipe), sum(c for _, c in to_wipe)))
    for name, count in sorted(to_wipe, key=lambda x: -x[1]):
        if count:
            print("  %-34s %6d rows" % (name, count))
    if views:
        print("\nskipping %d view(s): %s" % (len(views), ', '.join(views)))

    if not apply_it:
        print("\nDry run. Nothing was written. Re-run with --apply to do it.")
        return

    # Truncate rather than delete: it resets AUTO_INCREMENT, so the first new
    # request is #1 again, which is what "factory" is supposed to mean. Foreign
    # keys are off for the duration because the order would otherwise have to be
    # perfect and every future table would have to be added to it.
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for name, _ in to_wipe:
        cur.execute("TRUNCATE TABLE `%s`" % name)
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    print("\nWritten. %d table(s) emptied." % len(to_wipe))

    cur.close()
    conn.close()


if __name__ == '__main__':
    main('--apply' in sys.argv)
