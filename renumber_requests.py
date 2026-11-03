#!/usr/bin/env python
"""
Renumber sales requests from 502 (Gamal, 2026-11-02; Ahmed chose to renumber
the existing ones too).

Request numbers jumped (15 requests, 23645 to 47309) because the test suite
ran on the live database and MySQL never hands an AUTO_INCREMENT value back.
The tests now have their own database (tests/run.sh), so the numbers will stay
in sequence once they are put back in one: existing requests become 502, 503,
... in the order they were created, and the next new one follows the last.

Everything that points at a request moves with it, in one transaction:
every foreign key to sales_request, the four request columns without one,
the request chat threads ("sr:<id>"), and in Mongo the notifications' links and
"#044073"-style numbers. Files on disk keep their paths (stored as strings).

Idempotent: a database whose requests already start at 502 in creation order
is left alone.

    branding_gate_VENV/bin/python renumber_requests.py --db branding_gate_test --dry-run
    branding_gate_VENV/bin/python renumber_requests.py --db branding_gate
"""

import argparse
import re

import MySQLdb
import MySQLdb.cursors

START = 502

# Request columns with no foreign key (checked by hand: their values are ids
# of sales_request rows). design_request_* request_id point at design_request.
NO_FK = [('costing_log', 'request_id'), ('sales_request_approvals', 'sales_request_id'),
         ('design_request', 'sales_request_id'), ('user_expense_tracking', 'sales_request_id')]
THREADS = [('chat_seen', 'thread'), ('chat_mute', 'thread'), ('chat_attachment', 'thread'),
           ('chat_group_member', 'room'), ('group_chat_message', 'room')]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    parser.add_argument('--mongo-db', default=None, help='defaults to --db')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    conn = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456", db=args.db, port=3306,
                           charset='utf8mb4', use_unicode=True, cursorclass=MySQLdb.cursors.DictCursor)
    cur = conn.cursor()
    cur.execute("SELECT id FROM sales_request ORDER BY created_at, id")
    old_ids = [r['id'] for r in cur.fetchall()]
    mapping = {old: START + n for n, old in enumerate(old_ids)}
    if all(old == new for old, new in mapping.items()):
        print('already numbered from %d' % START)
        return
    clash = set(mapping.values()) & (set(old_ids) - set(k for k, v in mapping.items() if k == v))
    if clash:
        raise SystemExit('new numbers collide with existing ids: %s' % sorted(clash))
    for old, new in mapping.items():
        print('%6d -> %d' % (old, new))

    cur.execute("""SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE
                   WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME = 'sales_request'
                     AND REFERENCED_COLUMN_NAME = 'id'""", (args.db,))
    columns = sorted({(r['TABLE_NAME'], r['COLUMN_NAME']) for r in cur.fetchall()} | set(NO_FK))
    if args.dry_run:
        print('would update', len(columns), 'columns:', ', '.join('%s.%s' % c for c in columns))
        return

    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    case = ' '.join('WHEN %d THEN %d' % (o, n) for o, n in mapping.items())
    ids = ','.join(str(o) for o in mapping)
    cur.execute("UPDATE sales_request SET id = CASE id %s END WHERE id IN (%s)" % (case, ids))
    for table, column in columns:
        cur.execute("UPDATE `%s` SET `%s` = CASE `%s` %s END WHERE `%s` IN (%s)"
                    % (table, column, column, case, column, ids))
        if cur.rowcount:
            print('  %s.%s: %d' % (table, column, cur.rowcount))
    for table, column in THREADS:
        for old, new in mapping.items():
            cur.execute("UPDATE `%s` SET `%s` = %%s WHERE `%s` = %%s" % (table, column, column),
                        ('sr:%d' % new, 'sr:%d' % old))
    cur.execute("ALTER TABLE sales_request AUTO_INCREMENT = %d" % (START + len(old_ids)))
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()

    import pymongo
    notes = pymongo.MongoClient(serverSelectionTimeoutMS=3000)[args.mongo_db or args.db].notifications
    changed = 0
    for old, new in mapping.items():
        swaps = [(re.compile(r'request=%d(?!\d)' % old), 'request=%d' % new),
                 (re.compile(r'#0*%d(?!\d)' % old), '#%06d' % new)]
        for doc in notes.find({'$or': [{f: {'$regex': str(old)}} for f in ('link', 'title', 'content')]}):
            update = {}
            for field in ('link', 'title', 'content'):
                value = doc.get(field)
                if isinstance(value, str):
                    for pattern, repl in swaps:
                        value = pattern.sub(repl, value)
                    if value != doc.get(field):
                        update[field] = value
            if update:
                notes.update_one({'_id': doc['_id']}, {'$set': update})
                changed += 1
    print('notifications updated:', changed)
    print('next request number:', START + len(old_ids))


if __name__ == '__main__':
    main()
