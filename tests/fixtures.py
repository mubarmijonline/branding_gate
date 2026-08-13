"""
Rows a test needs, made by the test.

These suites used to borrow whatever client, supplier or payment method
happened to be in the database. That worked until the factory reset emptied it,
and then eight of them failed on `cur.fetchone()["id"]` with nothing to fetch --
a test that depends on production data is a test that fails for reasons that
have nothing to do with the code.

Everything here is created inside the caller's own transaction, which their
tearDown rolls back, so nothing survives the run.
"""


def ensure_client(cur, name='Fixture Client'):
    """A client id, making one if the table is empty."""
    cur.execute("SELECT id FROM client ORDER BY id LIMIT 1")
    row = cur.fetchone()
    if row:
        return row['id']
    cur.execute("""
        INSERT INTO client (client_name, mobile_number, email_address, added_by)
        VALUES (%s, '01000000000', 'fixture@example.com', 'fixtures')
    """, (name,))
    return cur.lastrowid


def ensure_suppliers(cur, how_many=1):
    """`how_many` supplier ids, topping the table up rather than skipping."""
    cur.execute("SELECT id FROM supplier ORDER BY id LIMIT %s", (how_many,))
    ids = [row['id'] for row in cur.fetchall()]
    while len(ids) < how_many:
        cur.execute("""
            INSERT INTO supplier (supplier_name, email_address, status, added_by)
            VALUES (%s, %s, 'Active', 'fixtures')
        """, ('Fixture Supplier %d' % (len(ids) + 1),
              'supplier%d@example.com' % (len(ids) + 1)))
        ids.append(cur.lastrowid)
    return ids


def ensure_payment_method(cur):
    """A payment method with money on it, for the flows that move some."""
    cur.execute("SELECT id, current_balance FROM payment_methods LIMIT 1")
    row = cur.fetchone()
    if row:
        return row
    cur.execute("""
        INSERT INTO payment_methods (method_name, method_code, current_balance, is_active)
        VALUES ('Fixture Cash', 'FIXTURE-CASH', 100000.00, 1)
    """)
    return {'id': cur.lastrowid, 'current_balance': 100000.00}


def ensure_sales_request(cur, owner_id, client_id=None, title='Fixture request'):
    """A sales request to hang items off."""
    cur.execute("SELECT id FROM sales_request ORDER BY id LIMIT 1")
    row = cur.fetchone()
    if row:
        return row['id']
    cur.execute("""
        INSERT INTO sales_request (client_id, title, start_date, created_by,
                                   items_count, owner_user_id)
        VALUES (%s, %s, CURDATE(), 'fixtures', 0, %s)
    """, (client_id or ensure_client(cur), title, owner_id))
    return cur.lastrowid
