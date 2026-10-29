#!/usr/bin/env python
"""
Repair requests created through the urgent-date approval before 2026-10-30.

That path stored the form payload ({instances, flat_fields}) as request_data
and wrote no sales_request_template_instances rows, so the edit form opened
with no items and no place fields (Gamal, 37125). This stores them the way the
add route does. The item rows themselves were always there and are not
touched: those requests are costed and priced, and their numbers stay.
Idempotent: a request that already has instance rows is skipped.

    branding_gate_VENV/bin/python request_instances_backfill.py --dry-run
    branding_gate_VENV/bin/python request_instances_backfill.py
"""

import argparse
import json

import MySQLdb
import MySQLdb.cursors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--db', default='branding_gate')
    args = parser.parse_args()
    conn = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456", db=args.db, port=3306,
                           charset='utf8mb4', use_unicode=True, cursorclass=MySQLdb.cursors.DictCursor)
    cur = conn.cursor()
    cur.execute("""
        SELECT sr.id, sr.request_type, sr.request_data FROM sales_request sr
        WHERE NOT EXISTS (SELECT 1 FROM sales_request_template_instances t WHERE t.request_id = sr.id)
    """)
    for row in cur.fetchall():
        try:
            data = json.loads(row['request_data'] or '{}')
        except ValueError:
            continue
        instances = data.get('instances') if isinstance(data, dict) else None
        if not instances or data.get('template_instances'):
            continue
        stored = {'request_types': [t for t in (row['request_type'] or '').split(',') if t],
                  'template_fields': data.get('flat_fields') or {},
                  'template_instances': instances}
        print('request %d: %d instance(s)' % (row['id'], len(instances)))
        if args.dry_run:
            continue
        cur.execute("UPDATE sales_request SET request_data = %s WHERE id = %s", (json.dumps(stored), row['id']))
        for order, instance in enumerate(instances):
            cur.execute("""
                INSERT INTO sales_request_template_instances
                    (request_id, template_id, request_type, instance_order, template_data)
                VALUES (%s, %s, %s, %s, %s)
            """, (row['id'], instance.get('template_id'), instance.get('request_type'), order,
                  json.dumps(instance.get('fields') or {})))
    if not args.dry_run:
        conn.commit()


if __name__ == '__main__':
    main()
