"""
Put every item's dimensions into metres.

The form used to take centimetres and divide by 100 on the way in, while the
edit form loaded the stored metres straight back into the same box -- so a
re-saved item shrank another hundredfold. Dimensions are metres everywhere now,
which leaves two kinds of wrong row behind:

  * hundreds and thousands -- centimetres that were never divided
  * hundredths -- metres that were divided twice

Only the dimensions named in `dimension_calc` matter; an unused one is noise and
is rescaled with the rest so the row stays self-consistent.

Rescaling changes the multiplier, so `total_cost` and `total_sell` are
recomputed through the same formulas the application uses. That moves money on
requests that may already be approved, which is why nothing is written without
--apply, and why a row whose corrected size is still implausible is skipped for
somebody to look at rather than guessed.

    ./branding_gate_VENV/bin/python fix_dimension_units.py            # dry run
    ./branding_gate_VENV/bin/python fix_dimension_units.py --apply

No DDL, so the whole thing is one transaction and --dry-run really is dry.
"""

import argparse
import json
import sys

import MySQLdb
import MySQLdb.cursors

# The application's own formula, so a rebuilt total can never disagree with the
# one the pages compute.
from branding_gate import item_total_cost

# Anything at or above this, in metres, is centimetres somebody never converted.
CENTIMETRE_FLOOR = 100.0
# Anything below this is a metre value that was divided by a hundred twice.
DOUBLE_DIVIDED_CEILING = 0.1
# A corrected dimension larger than this is not a stage or a screen; it is a
# typo, and no rule here can tell what was meant.
IMPLAUSIBLE_METRES = 60.0

DIMENSIONS = ('width', 'height', 'depth')


def connect():
    return MySQLdb.connect(
        host="localhost", user="ps", passwd="Aa@123456", db="branding_gate",
        port=3306, charset="utf8mb4", use_unicode=True,
        cursorclass=MySQLdb.cursors.DictCursor,
    )


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def used_dimensions(dimension_calc):
    """Which of width/height/depth the item's own formula multiplies."""
    calc = (dimension_calc or '').replace('*', '').replace(' ', '').upper()
    letters = {'W': 'width', 'H': 'height', 'D': 'depth'}
    return [letters[c] for c in calc if c in letters]


def scale_for(values):
    """
    The factor this row needs, or None when it already reads as metres.

    Decided on the dimensions the item actually multiplies: a stray depth of
    500 on a width x height item says nothing about the size of the item.
    """
    live = [v for v in values if v]
    if not live:
        return None
    if max(live) >= CENTIMETRE_FLOOR:
        return 0.01
    if max(live) < DOUBLE_DIVIDED_CEILING:
        return 100.0
    return None


def plan_row(row):
    """Return (scale, new_attributes, note) for one item, or None to leave it."""
    attributes = row['attributes']
    if isinstance(attributes, (bytes, bytearray)):
        attributes = attributes.decode('utf-8')
    try:
        data = json.loads(attributes) if attributes else {}
    except ValueError:
        return None, None, 'attributes is not JSON'
    if not isinstance(data, dict):
        return None, None, 'attributes is not an object'

    counted = used_dimensions(row['dimension_calc'])
    scale = scale_for([as_float(data.get(name)) for name in counted])
    if not scale:
        return None, None, None

    updated = dict(data)
    for name in DIMENSIONS:
        value = as_float(data.get(name))
        if value:
            updated[name] = round(value * scale, 4)

    corrected = [updated[name] for name in counted if as_float(updated.get(name))]
    if corrected and max(corrected) > IMPLAUSIBLE_METRES:
        return None, None, ('would become %s m -- too big to be a real size, '
                            'left alone' % max(corrected))
    return scale, updated, None


def item_for_formula(row, attributes):
    """The shape item_total_cost expects, with the corrected dimensions."""
    item = dict(row)
    item.update({name: attributes.get(name) for name in DIMENSIONS})
    return item


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true',
                        help='write the changes (default is a dry run)')
    args = parser.parse_args()

    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, request_id, name, attributes, dimension_calc, qty,
               cost_per_item, sell_per_item, total_cost, total_sell,
               sell_type, rental_days, include_days_in_calc, include_qty_in_calc
        FROM sales_request_items
        WHERE dimension_calc IS NOT NULL AND dimension_calc != ''
        ORDER BY id
    """)
    rows = cur.fetchall()

    changed, skipped = [], []
    for row in rows:
        scale, updated, note = plan_row(row)
        if note:
            skipped.append((row, note))
            continue
        if not scale:
            continue

        item = item_for_formula(row, updated)
        new_total_cost = (item_total_cost(item, row['cost_per_item'])
                          if row['cost_per_item'] is not None else None)
        new_total_sell = (item_total_cost(item, row['sell_per_item'])
                          if row['sell_per_item'] is not None else None)
        changed.append((row, updated, new_total_cost, new_total_sell))

    for row, updated, new_total_cost, new_total_sell in changed:
        print('item %s (request %s) %s' % (row['id'], row['request_id'], row['name']))
        print('  %s  ->  %s' % (
            ' x '.join('%s=%s' % (n, row_dimension(row, n)) for n in DIMENSIONS),
            ' x '.join('%s=%s' % (n, updated.get(n)) for n in DIMENSIONS)))
        if row['cost_per_item'] is not None:
            print('  total cost  %s -> %s' % (row['total_cost'], round(new_total_cost, 2)))
        if row['sell_per_item'] is not None:
            print('  total sell  %s -> %s' % (row['total_sell'], round(new_total_sell, 2)))

    for row, note in skipped:
        print('SKIPPED item %s (request %s) %s: %s'
              % (row['id'], row['request_id'], row['name'], note))

    print('\n%d item(s) to correct, %d left for review, %d already in metres.'
          % (len(changed), len(skipped), len(rows) - len(changed) - len(skipped)))

    if not args.apply:
        print('Dry run. Nothing was written. Re-run with --apply to write it.')
        cur.close()
        conn.close()
        return 0

    for row, updated, new_total_cost, new_total_sell in changed:
        cur.execute("""
            UPDATE sales_request_items
            SET attributes = %s, total_cost = %s, total_sell = %s
            WHERE id = %s
        """, (json.dumps(updated),
              None if new_total_cost is None else round(new_total_cost, 2),
              None if new_total_sell is None else round(new_total_sell, 2),
              row['id']))
    conn.commit()
    print('Written.')

    # The request totals are sums of their items, so they move too.
    request_ids = sorted({row['request_id'] for row, _u, _c, _s in changed})
    for request_id in request_ids:
        cur.execute("""
            UPDATE sales_request r
            SET r.total_cost = COALESCE((SELECT SUM(i.total_cost)
                                         FROM sales_request_items i
                                         WHERE i.request_id = r.id), 0),
                r.total_sell = COALESCE((SELECT SUM(i.total_sell)
                                         FROM sales_request_items i
                                         WHERE i.request_id = r.id), 0)
            WHERE r.id = %s
        """, (request_id,))
    conn.commit()
    print('Request totals rebuilt for %d request(s).' % len(request_ids))
    cur.close()
    conn.close()
    return 0


def row_dimension(row, name):
    attributes = row['attributes']
    if isinstance(attributes, (bytes, bytearray)):
        attributes = attributes.decode('utf-8')
    try:
        return (json.loads(attributes) or {}).get(name)
    except ValueError:
        return None


if __name__ == '__main__':
    sys.exit(main())
