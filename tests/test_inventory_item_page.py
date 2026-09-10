"""
One item, as a page of its own.

Tapping a line of stock opened a pop-up over the list. It now opens
/inventory/item/<id>: the item's details, every movement in and out, its
history, and stock in / out on the same screen -- drawn for what the account
may do, and refilled from the server after every movement so what it shows is
what the database now holds.

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


class InventoryItemPageTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4",
                                   use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self._cursor())
        branding_gate.app.config['TESTING'] = True
        self._real_notify = branding_gate.notify_users
        branding_gate.notify_users = lambda ids, title, body, link=None: len(ids)

        cur = self._cursor()
        cur.execute("""INSERT INTO entities (entity_name, entity_code, status, created_by)
                       VALUES ('Page Probe', 'PAGE-PROBE', 'active', 'tests')""")
        self.entity = cur.lastrowid
        cur.close()

        body = self._client('admin').post('/api/inventory/items/add', json={
            'item_name': 'Page Probe Item', 'unit_of_measure': 'PCS',
            'minimum_stock_level': '10', 'quantity_in_stock': '40',
            'average_cost': '5', 'entity_id': self.entity}).get_json()
        self.item_id = body['item_id']

    def tearDown(self):
        branding_gate.notify_users = self._real_notify
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _user_with(self, role_code):
        cur = self._cursor()
        cur.execute("""SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
                       WHERE r.code = %s ORDER BY u.id LIMIT 1""", (role_code,))
        row = cur.fetchone()
        cur.close()
        return row['id'] if row else None

    def _client(self, role_code):
        user_id = 1 if role_code == 'admin' else self._user_with(role_code)
        if user_id is None:
            self.skipTest('no %s account to test with' % role_code)
        perms, role = branding_gate.load_permissions(user_id)
        client = branding_gate.app.test_client()
        with client.session_transaction() as flask_session:
            flask_session.update({'user_id': user_id, 'mobile': 'm', 'email': 'e',
                                  'username': 'u', 'name': 'n', 'roles': [role],
                                  'perms': perms, 'role_code': role})
        return client

    def _page(self, role_code):
        response = self._client(role_code).get('/inventory/item/%d' % self.item_id)
        self.assertEqual(response.status_code, 200, role_code)
        return response.get_data(as_text=True)

    # --- the page ---------------------------------------------------------

    def test_the_page_is_the_item(self):
        page = self._page('admin')
        self.assertIn('Page Probe Item', page)
        self.assertIn('/inventory?entity_id=%d' % self.entity, page, 'the way back')
        self.assertIn('/api/inventory/items/${ITEM_ID}/timeline', page)

    def test_a_missing_item_is_a_404_not_an_empty_page(self):
        response = self._client('admin').get('/inventory/item/999999999')
        self.assertEqual(response.status_code, 404)

    def test_the_list_opens_the_page(self):
        with open('templates/inventory_management.html', encoding='utf-8') as handle:
            listing = handle.read()
        self.assertIn('const url = `/inventory/item/${data.id}`;', listing)
        # The pop-up it replaces is gone, not left behind unused.
        self.assertNotIn('itemLedgerModal', listing)
        self.assertNotIn('function openItemLedger(', listing)

    # --- drawn for the account --------------------------------------------

    def test_the_head_gets_everything(self):
        page = self._page('operations_manager')
        self.assertIn('id="ii_stock_form"', page)
        self.assertIn('id="ii_edit_btn"', page)
        self.assertIn('id="ii_delete_btn"', page)

    def test_a_leader_gets_everything_but_delete(self):
        page = self._page('operations_team_leader')
        self.assertIn('id="ii_stock_form"', page)
        self.assertIn('id="ii_edit_btn"', page)
        self.assertNotIn('id="ii_delete_btn"', page)

    def test_a_member_gets_stock_in_and_out_only(self):
        page = self._page('operations_member')
        self.assertIn('id="ii_stock_form"', page)
        self.assertNotIn('id="ii_edit_btn"', page)
        self.assertNotIn('id="ii_delete_btn"', page)
        self.assertNotIn('id="iiEditModal"', page)

    # --- what the form sends, and what comes back -------------------------

    def test_stock_in_and_out_from_the_page_move_the_figures(self):
        member = self._client('operations_member')
        response = member.post('/api/inventory/transactions/add',
                               json={'item_id': self.item_id, 'transaction_type': 'purchase',
                                     'quantity': 10, 'unit_cost': 8})
        self.assertEqual(response.status_code, 200, response.data[:200])
        response = member.post('/api/inventory/transactions/add',
                               json={'item_id': self.item_id, 'transaction_type': 'stock_out',
                                     'quantity': 5, 'unit_cost': 0})
        self.assertEqual(response.status_code, 200, response.data[:200])

        item = member.get('/api/inventory/items/%d' % self.item_id).get_json()['item']
        self.assertEqual(float(item['quantity_in_stock']), 45.0)
        # 40 at 5 then 10 at 8: (200 + 80) / 50 = 5.6. A stock-out does not move it.
        self.assertAlmostEqual(float(item['average_cost']), 5.6, places=2)

        moves = [e for e in member.get('/api/inventory/items/%d/timeline' % self.item_id)
                 .get_json()['timeline'] if e['kind'] == 'stock']
        self.assertEqual(len(moves), 3)

    def test_a_member_still_cannot_edit_or_delete_through_the_api(self):
        member = self._client('operations_member')
        self.assertEqual(member.put('/api/inventory/items/%d' % self.item_id,
                                    json={'minimum_stock_level': '1'}).status_code, 403)
        self.assertEqual(member.delete('/api/inventory/items/%d' % self.item_id).status_code, 403)

    def test_the_page_refills_from_the_server_after_a_movement(self):
        with open('templates/inventory_item.html', encoding='utf-8') as handle:
            page = handle.read()
        # After a movement the page asks again rather than doing sums itself.
        submit = page[page.index('function submitStock('):page.index('// --- edit and delete')]
        self.assertIn("fetch('/api/inventory/transactions/add'", submit)
        self.assertIn('return load({ newestAt: startedAt });', submit)
        # A stock-out larger than the shelf is stopped before it is sent.
        self.assertIn("if (kind === 'out' && qty > stock)", submit)

    def test_the_page_uses_the_shared_stock_reading(self):
        with open('templates/inventory_item.html', encoding='utf-8') as handle:
            page = handle.read()
        with open('templates/inventory_management.html', encoding='utf-8') as handle:
            listing = handle.read()
        for template in (page, listing):
            self.assertIn("filename='js/bg-stock.js'", template)
        self.assertIn('bgStockState(item)', page)


class TableDragDoesNotEatClicksTest(unittest.TestCase):
    """
    A click on a row must reach the row.

    main.html makes any sideways-scrollable table draggable. It took the
    pointer and called preventDefault on pointerdown itself, so the browser
    sent every click inside such a table to the wrapper, not the row -- and a
    row that opens its item on click did nothing at all. It showed up as soon
    as the inventory table was a pixel wider than its box. Measured live: the
    press landed on the cell, no mousedown or mouseup followed, and the click
    arrived on the wrapper DIV.
    """

    def setUp(self):
        with open('templates/main.html', encoding='utf-8') as handle:
            page = handle.read()
        start = page.index("$(document).on('pointerdown.bgTableDrag'")
        self.handler = page[start:page.index('function openSettleCustodyModal', start)]
        self.press = self.handler[:self.handler.index('function endDrag(')]

    def test_a_press_takes_nothing(self):
        # Nothing between the press and the first real movement may take the
        # pointer or cancel the press.
        self.assertNotIn('setPointerCapture', self.press)
        self.assertNotIn('e.preventDefault()', self.press)

    def test_the_pointer_is_taken_only_once_it_moves_like_a_drag(self):
        move = self.handler[self.handler.index("'pointermove.bgTableDragMove'"):]
        self.assertIn('if (Math.abs(dx) < 6) return;', move)
        self.assertLess(move.index('if (Math.abs(dx) < 6) return;'),
                        move.index('setPointerCapture'))

    def test_only_a_real_drag_swallows_its_click(self):
        end = self.handler[self.handler.index('function endDrag('):]
        self.assertLess(end.index('if (!drag.active) return;'), end.index('swallow'))

    def test_touch_is_left_to_the_browser(self):
        self.assertIn("if (event.pointerType === 'touch') return;", self.press)


if __name__ == '__main__':
    unittest.main()
