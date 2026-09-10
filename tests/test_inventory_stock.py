"""
Stock and cost on an inventory item: who is allowed to decide them.

Three things were editable that should never have been:

  * `average_cost` was posted by the add form and written straight onto the
    row. The database trigger recomputes it as the weighted average of the
    purchases on every movement, so a typed figure was either about to be
    overwritten or -- with no opening stock behind it -- a cost for an item
    nobody had ever bought.
  * `total_cost` on a transaction was posted too, and it feeds that same
    average. A total that disagreed with quantity x unit cost moved the item's
    cost to a number nothing was paid at.
  * the minimum quantity was optional, defaulting to zero, which is the one
    value that switches the low-stock flag off entirely.

And renaming an item onto another one in the same entity went through without
a word, leaving two rows for one thing, each with its own stock -- which is
what later made an add refuse with a code nobody could see.

Rollback-based, like the other route tests here.
"""

import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def close(self): pass


class InventoryStockAndCostTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4",
                                   use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self._cursor())
        branding_gate.app.config['TESTING'] = True

        cur = self._cursor()
        cur.execute("""INSERT INTO entities (entity_name, entity_code, status, created_by)
                       VALUES ('Stock Test', 'STOCK-TEST', 'active', 'tests')""")
        self.entity = cur.lastrowid
        cur.close()

        perms, role_code = branding_gate.load_permissions(1)
        self.client = branding_gate.app.test_client()
        with self.client.session_transaction() as flask_session:
            flask_session.update({'user_id': 1, 'mobile': 'm', 'email': 'e',
                                  'username': 'u', 'name': 'n', 'roles': [role_code],
                                  'perms': perms, 'role_code': role_code})

    def tearDown(self):
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _add(self, name, **extra):
        payload = {'item_name': name, 'unit_of_measure': 'PCS',
                   'minimum_stock_level': '10', 'quantity_in_stock': '0',
                   'entity_id': self.entity}
        payload.update(extra)
        return self.client.post('/api/inventory/items/add', json=payload)

    def _row(self, item_id):
        cur = self._cursor()
        cur.execute("""SELECT quantity_in_stock, average_cost, minimum_stock_level
                       FROM inventory_items WHERE id = %s""", (item_id,))
        row = cur.fetchone()
        cur.close()
        return row

    # --- the minimum ------------------------------------------------------

    def test_the_minimum_is_required_when_adding_an_item(self):
        response = self.client.post('/api/inventory/items/add',
                                    json={'item_name': 'No Minimum Probe',
                                          'unit_of_measure': 'PCS',
                                          'entity_id': self.entity})
        self.assertEqual(response.status_code, 400)
        self.assertIn('Minimum quantity', response.get_json()['error'])

    def test_the_minimum_is_asked_for_on_the_item_not_on_a_movement(self):
        with open('templates/inventory_management.html', encoding='utf-8') as handle:
            page = handle.read()
        add_form = page[page.index('<form id="addItemForm">'):]
        add_form = add_form[:add_form.index('</form>')]
        self.assertIn('name="minimum_stock_level" required', add_form)
        # ...and nowhere in the movement form, which is per transaction.
        movement = page[page.index('<form id="addTransactionForm">'):]
        movement = movement[:movement.index('</form>')]
        self.assertNotIn('minimum_stock_level', movement)

    # --- the average cost -------------------------------------------------

    def test_a_typed_cost_with_no_stock_behind_it_is_not_kept(self):
        body = self._add('Typed Cost Probe', average_cost='99', quantity_in_stock='0').get_json()
        self.assertEqual(float(self._row(body['item_id'])['average_cost']), 0.0,
                         'a cost was recorded for an item nothing was bought for')

    def test_the_opening_purchase_is_what_sets_the_cost(self):
        body = self._add('Opening Cost Probe', average_cost='25',
                         quantity_in_stock='4').get_json()
        row = self._row(body['item_id'])
        self.assertEqual(float(row['quantity_in_stock']), 4.0)
        self.assertEqual(float(row['average_cost']), 25.0)
        # ...and it arrived as a movement, like every later one.
        cur = self._cursor()
        cur.execute("""SELECT transaction_type, quantity, total_cost FROM inventory_transactions
                       WHERE item_id = %s""", (body['item_id'],))
        movements = cur.fetchall()
        cur.close()
        self.assertEqual([m['transaction_type'] for m in movements], ['purchase'])
        self.assertEqual(float(movements[0]['total_cost']), 100.0)

    def test_a_second_purchase_averages_rather_than_replaces(self):
        body = self._add('Averaging Probe', average_cost='10',
                         quantity_in_stock='10').get_json()
        response = self.client.post('/api/inventory/transactions/add',
                                    json={'item_id': body['item_id'],
                                          'transaction_type': 'purchase',
                                          'quantity': 10, 'unit_cost': 20})
        self.assertEqual(response.status_code, 200, response.data[:200])
        row = self._row(body['item_id'])
        self.assertEqual(float(row['quantity_in_stock']), 20.0)
        self.assertEqual(float(row['average_cost']), 15.0,
                         'ten at 10 and ten at 20 average 15')

    def test_a_posted_total_cannot_bend_the_average(self):
        body = self._add('Posted Total Probe', average_cost='10',
                         quantity_in_stock='10').get_json()
        # Claiming a total of one million for ten units at twenty.
        self.client.post('/api/inventory/transactions/add',
                         json={'item_id': body['item_id'], 'transaction_type': 'purchase',
                               'quantity': 10, 'unit_cost': 20, 'total_cost': 1000000})
        cur = self._cursor()
        cur.execute("""SELECT total_cost FROM inventory_transactions
                       WHERE item_id = %s ORDER BY id DESC LIMIT 1""", (body['item_id'],))
        total = float(cur.fetchone()['total_cost'])
        cur.close()
        self.assertEqual(total, 200.0)
        self.assertEqual(float(self._row(body['item_id'])['average_cost']), 15.0)

    def test_an_edit_cannot_set_the_cost_or_the_stock(self):
        body = self._add('Edit Guard Probe', average_cost='10',
                         quantity_in_stock='10').get_json()
        response = self.client.put('/api/inventory/items/%d' % body['item_id'],
                                   json={'item_name': 'Edit Guard Probe',
                                         'average_cost': '500',
                                         'quantity_in_stock': '9999',
                                         'minimum_stock_level': '7'})
        self.assertEqual(response.status_code, 200, response.data[:200])
        row = self._row(body['item_id'])
        self.assertEqual(float(row['average_cost']), 10.0, 'the cost was edited')
        self.assertEqual(float(row['quantity_in_stock']), 10.0, 'the stock was edited')
        self.assertEqual(float(row['minimum_stock_level']), 7.0,
                         'the minimum, which is the item\'s own, should change')

    # --- the rename that made two of one item -----------------------------

    def test_an_edit_cannot_rename_one_item_onto_another(self):
        first = self._add('Rename Target Probe').get_json()
        second = self._add('Rename Source Probe').get_json()
        response = self.client.put('/api/inventory/items/%d' % second['item_id'],
                                   json={'item_name': 'Rename Target Probe'})
        self.assertEqual(response.status_code, 400)
        error = response.get_json()['error']
        self.assertIn(first['item_code'], error,
                      'the message should name the item already holding it')
        cur = self._cursor()
        cur.execute("""SELECT COUNT(*) n FROM inventory_items
                       WHERE item_name = 'Rename Target Probe' AND entity_id = %s""",
                    (self.entity,))
        self.assertEqual(cur.fetchone()['n'], 1)
        cur.close()

    def test_saving_an_item_unchanged_is_not_a_duplicate(self):
        body = self._add('Unchanged Probe').get_json()
        response = self.client.put('/api/inventory/items/%d' % body['item_id'],
                                   json={'item_name': 'Unchanged Probe',
                                         'unit_of_measure': 'PCS',
                                         'minimum_stock_level': '10',
                                         'width': '', 'height': '', 'depth': ''})
        self.assertEqual(response.status_code, 200, response.data[:200])
        self.assertTrue(response.get_json()['success'])

    # --- what the page shows about a low item -----------------------------

    def test_the_page_flags_an_item_at_or_below_its_minimum(self):
        with open('templates/inventory_management.html', encoding='utf-8') as handle:
            page = handle.read()
        self.assertIn('function stockState(', page)
        for label in ('Below Minimum', 'Near Minimum', 'Out of Stock'):
            self.assertIn(label, page)
        # The flag, and the figure carrying it rather than only the status cell.
        self.assertIn('fa-flag', page)
        self.assertIn('function renderStockCell(', page)
        self.assertIn('.stock-below, .stock-out { color: var(--danger); }', page)

    def test_an_item_opens_its_own_movements(self):
        with open('templates/inventory_management.html', encoding='utf-8') as handle:
            page = handle.read()
        self.assertIn('id="itemLedgerModal"', page)
        self.assertIn('function openItemLedger(', page)
        self.assertIn('/api/inventory/transactions?item_id=', page)
        # The whole row, not one word of it.
        self.assertIn('function attachRowOpensItem(', page)
        self.assertIn('openItemLedger(data.id)', page)
        self.assertIn('tr.row-openable { cursor: pointer; }', page)
        # ...and the action buttons still do their own thing.
        self.assertIn(".closest('.row-actions, a, button, input, select, label')", page)

    def test_the_movements_api_can_be_asked_for_one_item(self):
        body = self._add('Ledger Probe', average_cost='5',
                         quantity_in_stock='3').get_json()
        response = self.client.get('/api/inventory/transactions?item_id=%d'
                                   % body['item_id'])
        self.assertEqual(response.status_code, 200)
        movements = response.get_json()['transactions']
        self.assertEqual(len(movements), 1)
        self.assertEqual(movements[0]['transaction_type'], 'purchase')
        self.assertEqual(movements[0]['balance_after'], 3.0)


if __name__ == '__main__':
    unittest.main()
