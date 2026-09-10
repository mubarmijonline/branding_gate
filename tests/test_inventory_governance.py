"""
Who may do what to an item, and what the item remembers about it.

Three separate complaints, one subject:

  * Deleting an item was open to anyone who could edit one. It is the Head's
    call alone -- a delete takes a row and its history with it -- while the
    team leader does everything else, and a member moves stock and nothing
    more. Members could not even do that: they held `inventory.view` and
    nothing else, so the stock they physically move could not be recorded.
  * `created_by` held a bare username and there was no `updated_by` at all, so
    a row said `01050172555` and nothing about the edit made yesterday.
  * A minimum quantity that nothing watches is decoration. A movement that
    takes an item to or under it now tells the whole Operations team, once, on
    the crossing -- the fifth stock-out from an item everyone has been told
    about is noise, and noise is how a real warning gets ignored.

Rollback-based, like the other route tests here.
"""

import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate
import rbac


class RolesOnInventoryTest(unittest.TestCase):
    """The matrix itself, before any route is called."""

    def _inventory(self, role):
        return {code.split('.')[1]: scope
                for code, scope in rbac.SEED_MATRIX[role].items()
                if code.startswith('inventory.')}

    def test_only_the_head_deletes(self):
        holders = {role for role, perms in rbac.SEED_MATRIX.items()
                   if 'inventory.delete' in perms}
        self.assertEqual(holders, {'admin', 'operations_manager'},
                         'delete is the Operations Head\'s, and the owner\'s')

    def test_the_leader_does_everything_but_delete(self):
        head = self._inventory('operations_manager')
        leader = self._inventory('operations_team_leader')
        self.assertEqual(set(head) - set(leader), {'delete'})
        for permission, scope in leader.items():
            self.assertEqual(head[permission], scope, permission)

    def test_a_member_moves_stock_and_nothing_else(self):
        member = self._inventory('operations_member')
        self.assertEqual(set(member), {'view', 'transact'})

    def test_the_page_draws_what_the_account_may_do(self):
        with open('templates/inventory_management.html', encoding='utf-8') as handle:
            page = handle.read()
        # The buttons the routes guard are guarded on the page too, so a
        # member is not offered an Edit that would come back 403.
        self.assertIn("{% if 'inventory.create' in _p %}", page)
        self.assertIn("{% if 'inventory.transact' in _p %}", page)
        self.assertIn('if (CAN.remove) {', page)
        self.assertIn('if (CAN.edit) {', page)
        self.assertIn("remove:   {{ ('inventory.delete' in _p)|tojson }}", page)


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def close(self): pass


class ItemHistoryTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4",
                                   use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self._cursor())
        branding_gate.app.config['TESTING'] = True

        self.sent = []
        self._real_notify = branding_gate.notify_users
        branding_gate.notify_users = lambda ids, title, body, link=None: (
            self.sent.append({'to': sorted(ids), 'title': title,
                              'body': body, 'link': link}) or len(ids))

        cur = self._cursor()
        cur.execute("""INSERT INTO entities (entity_name, entity_code, status, created_by)
                       VALUES ('History Probe', 'HISTORY-PROBE', 'active', 'tests')""")
        self.entity = cur.lastrowid
        cur.execute("SELECT username, mobile, name FROM user WHERE id = 1")
        self.me = cur.fetchone()
        cur.close()

        perms, role_code = branding_gate.load_permissions(1)
        self.client = branding_gate.app.test_client()
        with self.client.session_transaction() as flask_session:
            flask_session.update({'user_id': 1, 'mobile': self.me['mobile'], 'email': 'e',
                                  'username': self.me['username'], 'name': self.me['name'],
                                  'roles': [role_code], 'perms': perms, 'role_code': role_code})

    def tearDown(self):
        branding_gate.notify_users = self._real_notify
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _add(self, name='History Probe Item', **extra):
        payload = {'item_name': name, 'unit_of_measure': 'PCS',
                   'minimum_stock_level': '50', 'quantity_in_stock': '100',
                   'average_cost': '10', 'entity_id': self.entity}
        payload.update(extra)
        return self.client.post('/api/inventory/items/add', json=payload).get_json()

    def _timeline(self, item_id):
        response = self.client.get('/api/inventory/items/%d/timeline' % item_id)
        self.assertEqual(response.status_code, 200, response.data[:200])
        return response.get_json()['timeline']

    def _move(self, item_id, kind, quantity):
        return self.client.post('/api/inventory/transactions/add',
                                json={'item_id': item_id, 'transaction_type': kind,
                                      'quantity': quantity}).get_json()

    # --- who did it -------------------------------------------------------

    def test_an_item_names_who_made_it_and_who_last_touched_it(self):
        item_id = self._add()['item_id']
        self.client.put('/api/inventory/items/%d' % item_id,
                        json={'minimum_stock_level': '80'})
        item = self.client.get('/api/inventory/items/%d' % item_id).get_json()['item']
        self.assertEqual(item['created_by_name'], self.me['name'])
        self.assertEqual(item['created_by_mobile'], self.me['mobile'])
        self.assertEqual(item['updated_by_name'], self.me['name'])
        self.assertEqual(item['updated_by_mobile'], self.me['mobile'])

    def test_the_list_names_them_too(self):
        self._add()
        items = self.client.get('/api/inventory/items?type=regular&entity_id=%d'
                                % self.entity).get_json()['items']
        self.assertTrue(items)
        self.assertEqual(items[0]['created_by_name'], self.me['name'])
        self.assertEqual(items[0]['created_by_mobile'], self.me['mobile'])

    def test_a_movement_names_who_made_it(self):
        item_id = self._add()['item_id']
        movements = self.client.get('/api/inventory/transactions?item_id=%d'
                                    % item_id).get_json()['transactions']
        self.assertEqual(movements[0]['performed_by_name'], self.me['name'])
        self.assertEqual(movements[0]['performed_by_mobile'], self.me['mobile'])

    # --- what happened ----------------------------------------------------

    def test_adding_an_item_starts_its_timeline(self):
        item_id = self._add()['item_id']
        entries = [e for e in self._timeline(item_id) if e['kind'] == 'item']
        self.assertEqual([e['event_type'] for e in entries], ['created'])
        self.assertEqual(entries[0]['by_name'], self.me['name'])
        self.assertEqual(entries[0]['by_mobile'], self.me['mobile'])

    def test_an_edit_records_the_field_and_both_values(self):
        item_id = self._add()['item_id']
        self.client.put('/api/inventory/items/%d' % item_id,
                        json={'minimum_stock_level': '80', 'category': 'Probe'})
        edits = {e['field_name']: e for e in self._timeline(item_id)
                 if e['event_type'] == 'edited'}
        self.assertEqual(set(edits), {'minimum_stock_level', 'category'})
        self.assertEqual(edits['minimum_stock_level']['old_value'], '50.0')
        self.assertEqual(edits['minimum_stock_level']['new_value'], '80.0')
        self.assertEqual(edits['minimum_stock_level']['field_label'], 'Minimum quantity')

    def test_an_edit_that_changes_nothing_records_nothing(self):
        item_id = self._add()['item_id']
        self.client.put('/api/inventory/items/%d' % item_id,
                        json={'minimum_stock_level': '50', 'item_name': 'History Probe Item'})
        self.assertEqual([e for e in self._timeline(item_id)
                          if e['event_type'] == 'edited'], [])

    def test_retiring_an_item_is_on_its_timeline(self):
        item_id = self._add()['item_id']
        outcome = self.client.delete('/api/inventory/items/%d' % item_id).get_json()
        if outcome.get('outcome') != 'discontinued':
            self.skipTest('nothing held this item, so it was really deleted')
        self.assertIn('retired', [e['event_type'] for e in self._timeline(item_id)])

    def test_the_movements_are_on_the_same_timeline(self):
        item_id = self._add()['item_id']
        self._move(item_id, 'stock_out', 5)
        kinds = [e['kind'] for e in self._timeline(item_id)]
        self.assertIn('stock', kinds)
        self.assertIn('item', kinds)

    # --- the minimum, watched --------------------------------------------

    def test_crossing_the_minimum_tells_the_operations_team(self):
        item_id = self._add()['item_id']          # 100 in stock, minimum 50
        self.assertEqual(self.sent, [], 'nothing to say while it is well stocked')
        told = self._move(item_id, 'stock_out', 60)   # down to 40
        self.assertTrue(told.get('low_stock_notified'))
        self.assertEqual(len(self.sent), 1)
        self.assertIn('Below minimum', self.sent[0]['title'])
        self.assertIn('/inventory?entity_id=%d' % self.entity, self.sent[0]['link'])

        cur = self._cursor()
        cur.execute("""SELECT u.id FROM user u JOIN department d ON d.id = u.department_id
                       WHERE d.code = 'operations'""")
        everyone = sorted(row['id'] for row in cur.fetchall())
        cur.close()
        self.assertEqual(self.sent[0]['to'], everyone,
                         'the whole team hears, not one owner')

    def test_it_is_said_once_not_on_every_movement_after(self):
        item_id = self._add()['item_id']
        self._move(item_id, 'stock_out', 60)      # crosses: one notification
        self._move(item_id, 'stock_out', 1)       # still low: nothing new
        self._move(item_id, 'stock_out', 1)
        self.assertEqual(len(self.sent), 1)

    def test_running_out_is_always_worth_saying(self):
        item_id = self._add()['item_id']
        self._move(item_id, 'stock_out', 60)      # below
        self._move(item_id, 'stock_out', 40)      # empty
        self.assertEqual(len(self.sent), 2)
        self.assertIn('Out of stock', self.sent[-1]['title'])

    def test_stock_coming_back_in_says_nothing(self):
        item_id = self._add()['item_id']
        self._move(item_id, 'purchase', 100)
        self.assertEqual(self.sent, [])


class InventoryOnAPhoneTest(unittest.TestCase):
    """
    The pages had desktop padding, four-across grids and no dialog rules.

    Not a rendering test -- it pins that each page carries a phone breakpoint
    and the specific rules that were missing, so they are not dropped by the
    next edit to a stylesheet nobody reads on a phone.
    """

    PAGES = ('inventory_management.html', 'item_management.html',
             'entity_management.html', 'inventory_selection.html')

    def _page(self, name):
        with open('templates/%s' % name, encoding='utf-8') as handle:
            return handle.read()

    def test_every_inventory_page_has_a_phone_breakpoint(self):
        for name in self.PAGES:
            self.assertIn('@media (max-width: 768px)', self._page(name), name)

    def test_the_dialogs_fit_the_screen(self):
        for name in ('inventory_management.html', 'item_management.html',
                     'entity_management.html'):
            page = self._page(name)
            self.assertIn('.modal-dialog { margin: 8px; max-width: none; }', page, name)

    def test_the_figures_sit_two_across_rather_than_one(self):
        self.assertIn('grid-template-columns: repeat(2, minmax(0, 1fr))',
                      self._page('inventory_management.html'))
        self.assertIn('grid-template-columns: repeat(2, minmax(0, 1fr))',
                      self._page('entity_management.html'))
        self.assertIn('flex: 0 0 50%; max-width: 50%',
                      self._page('item_management.html'))

    def test_the_row_buttons_are_big_enough_to_hit(self):
        page = self._page('inventory_management.html')
        self.assertIn('.row-actions .btn-action { width: 34px; height: 34px;', page)

    def test_the_tables_fold_their_columns_instead_of_overflowing(self):
        page = self._page('inventory_management.html')
        # The extension every table here already asked for, finally loaded...
        self.assertIn('responsive/2.5.0/js/dataTables.responsive.min.js', page)
        self.assertIn('responsivePriority: 1, targets: 1', page)
        # ...with nothing scrolling above it to tell it there is room. The
        # three DataTables lost that wrapper; the plain ledger table inside
        # the item view keeps it, because it really does scroll.
        for table in ('regularTable', 'creditTable', 'transTable'):
            before = page[:page.index('id="%s"' % table)]
            self.assertTrue(before.rstrip().endswith('style="width:100%"') or
                            '<div class="table-holder">' in before[-400:], table)
            self.assertNotIn('<div class="table-responsive">', before[-400:], table)
        with open('static/css/branding-gate-system.css', encoding='utf-8') as handle:
            css = handle.read()
        self.assertIn('table.dataTable.dtr-inline,', css)
        self.assertIn('  min-width: 0;', css)


if __name__ == '__main__':
    unittest.main()
