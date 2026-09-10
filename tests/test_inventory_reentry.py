"""
Adding an item back after removing it from an entity's inventory.

The client added an item inside an entity, removed it, then added it again and
was told it "already exists with INV-00002" -- a code they could not see
anywhere on the page. Two reasons, both in the same check:

  * the duplicate check, and the unique index behind it, ignored `entity_id`,
    so an item belonging to a different entity blocked the add; and
  * it matched rows that had been retired, which is what removing an item with
    movements behind it does. The thing they had just deleted was refusing to
    come back, and naming itself while doing it.

Scoped to the entity now, and a retired match is brought back with its history
rather than refused. Rollback-based, like the other route tests here.
"""

import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def close(self): pass


class InventoryReEntryTest(unittest.TestCase):

    NAME = 'Re-entry Probe Mug'

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4",
                                   use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self._cursor())
        branding_gate.app.config['TESTING'] = True

        cur = self._cursor()
        self.entity = self._make_entity(cur, 'Re-entry A')
        self.other_entity = self._make_entity(cur, 'Re-entry B')
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

    def _make_entity(self, cur, name):
        cur.execute("""INSERT INTO entities (entity_name, entity_code, status, created_by)
                       VALUES (%s, %s, 'active', 'tests')""",
                    (name, name.replace(' ', '-').upper()))
        return cur.lastrowid

    def _add(self, entity_id, **extra):
        payload = {'item_name': self.NAME, 'unit_of_measure': 'PCS',
                   'minimum_stock_level': '10', 'quantity_in_stock': '25',
                   'entity_id': entity_id}
        payload.update(extra)
        response = self.client.post('/api/inventory/items/add', json=payload)
        self.assertEqual(response.status_code, 200, response.data[:300])
        return response.get_json()

    def _delete(self, item_id):
        response = self.client.delete('/api/inventory/items/%d' % item_id)
        self.assertEqual(response.status_code, 200, response.data[:300])
        return response.get_json()

    def _row(self, item_id):
        cur = self._cursor()
        cur.execute("""SELECT status, quantity_in_stock, minimum_stock_level, entity_id
                       FROM inventory_items WHERE id = %s""", (item_id,))
        row = cur.fetchone()
        cur.close()
        return row

    def test_an_item_removed_from_an_entity_can_be_added_again(self):
        first = self._add(self.entity)
        removed = self._delete(first['item_id'])
        self.assertIn(removed.get('outcome'), ('deleted', 'discontinued'))

        again = self._add(self.entity, minimum_stock_level='40',
                          quantity_in_stock='15')
        self.assertFalse(again.get('already_exists'),
                         'the item they just removed is being refused: %s'
                         % again.get('message'))
        self.assertTrue(again.get('success'))

    def test_a_retired_item_comes_back_rather_than_doubling_up(self):
        first = self._add(self.entity)
        if self._delete(first['item_id']).get('outcome') != 'discontinued':
            self.skipTest('nothing held this item, so it was really deleted')

        again = self._add(self.entity, minimum_stock_level='40')
        self.assertTrue(again.get('revived'), again)
        self.assertEqual(again['item_id'], first['item_id'],
                         'the old row should come back, not a second one')
        self.assertEqual(again['item_code'], first['item_code'])
        row = self._row(first['item_id'])
        self.assertEqual(row['status'], 'active')
        self.assertEqual(int(row['minimum_stock_level']), 40,
                         'the values they typed on the second add should stick')

    def test_the_message_says_what_happened(self):
        first = self._add(self.entity)
        if self._delete(first['item_id']).get('outcome') != 'discontinued':
            self.skipTest('nothing held this item, so it was really deleted')
        again = self._add(self.entity)
        self.assertIn('retired', (again.get('message') or '').lower())
        # ...and both inventory pages show it rather than a bare "Created".
        with open('templates/inventory_management.html', encoding='utf-8') as handle:
            page = handle.read()
        self.assertIn('result.revived', page)
        self.assertIn('Item Restored', page)

    def test_one_entity_does_not_block_another(self):
        mine = self._add(self.entity)
        theirs = self._add(self.other_entity)
        self.assertFalse(theirs.get('already_exists'),
                         'the same item name in another entity is being refused')
        self.assertNotEqual(mine['item_id'], theirs['item_id'])
        self.assertEqual(self._row(theirs['item_id'])['entity_id'], self.other_entity)

    def test_a_live_item_in_the_same_entity_is_still_refused_once(self):
        self._add(self.entity)
        twice = self._add(self.entity)
        self.assertTrue(twice.get('already_exists'),
                        'adding the same live item twice should point at the first')

    def test_the_unique_index_is_scoped_to_the_entity(self):
        cur = self._cursor()
        cur.execute("SHOW INDEX FROM inventory_items WHERE Key_name = 'idx_unique_item'")
        columns = [row['Column_name'] for row in cur.fetchall()]
        cur.close()
        self.assertIn('entity_id', columns,
                      'without entity_id the index refuses an item another '
                      'entity already holds')


if __name__ == '__main__':
    unittest.main()
