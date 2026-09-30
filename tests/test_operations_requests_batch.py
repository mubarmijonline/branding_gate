"""
What David's Operations team asked for, after testing with it.

1. A client's approval is where Operations' work starts, and nobody was told:
   the item just appeared on Approved Items for whoever opened the page.
2. Approved Items: every request looked the same, and the table was a flat
   list of items. Each request now has its own colour, and the table is one
   row per request that expands to its items.
3. The exports carried columns nobody on site needs -- an internal id, the
   rent/sell type, what the item cost us, the supplier's email, the approval
   date -- and the costs should not reach a supplier at all. Which columns go
   out is now chosen, and those six are off unless asked for.
5. My Expenses: the supplier dropdown was empty for Operations. The list came
   from an endpoint only Finance could read, so it answered 403 and the page
   said nothing. It now opens to anyone who records an expense, defaults to
   Transportation, and "Other" saves the name typed rather than the word.

Rollback-based, like the other route tests here.
"""

import io
import os
import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate
import fixtures

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def close(self): pass


class _Harness(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        self._real_notify = branding_gate.notify_users
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self._cursor())
        branding_gate.app.config['TESTING'] = True
        self.sent = []
        branding_gate.notify_users = lambda ids, title, body, link=None: (
            self.sent.append({'to': sorted(int(i) for i in (ids or [])), 'title': title,
                              'body': body, 'link': link}) or len(ids or []))

    def _undo(self):
        branding_gate.notify_users = self._real_notify
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _client_for(self, user_id):
        perms, role_code = branding_gate.load_permissions(user_id)
        client = branding_gate.app.test_client()
        with client.session_transaction() as flask_session:
            flask_session.update({'user_id': user_id, 'mobile': 'm', 'email': 'e',
                                  'username': 'u', 'name': 'Tester', 'roles': [role_code],
                                  'perms': perms, 'role_code': role_code})
        return client

    def _user_with_role(self, role_code):
        cur = self._cursor()
        cur.execute("""SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
                       WHERE r.code = %s ORDER BY u.id LIMIT 1""", (role_code,))
        row = cur.fetchone()
        cur.close()
        if not row:
            self.skipTest('no %s account' % role_code)
        return row['id']

    def _request_with_item(self, approval_status='pending'):
        cur = self._cursor()
        client_id = fixtures.ensure_client(cur)
        cur.execute("""INSERT INTO sales_request (client_id, title, start_date, end_date, created_by,
                                                  items_count, owner_user_id)
                       VALUES (%s, 'Ops batch probe', '2026-10-10', '2026-10-12', 'probe', 1, 1)""",
                    (client_id,))
        request_id = cur.lastrowid
        cur.execute("""INSERT INTO sales_request_items
                           (request_id, name, qty, unit, cost_per_item, sell_per_item,
                            total_cost, total_sell, approval_status, sell_type, rental_days)
                       VALUES (%s, 'Ops probe item', 10, 'pcs', 80, 120, 800, 1200, %s, 'rent', 1)""",
                    (request_id, approval_status))
        item_id = cur.lastrowid
        cur.close()
        return request_id, item_id


class ClientApprovalTellsOperationsTest(_Harness):

    def test_the_whole_team_hears_with_a_link_to_the_request(self):
        request_id, item_id = self._request_with_item('pending')
        response = self._client_for(1).post('/api/client-approval/items/%d/approve' % item_id,
                                            json={'approved': True})
        self.assertEqual(response.status_code, 200, response.data[:300])

        told = [n for n in self.sent if n['title'].startswith('Client approved')]
        self.assertEqual(len(told), 1, 'one notice per approval')
        cur = self._cursor()
        everyone = branding_gate.operations_team_ids(cur)
        cur.close()
        self.assertTrue(everyone, 'there is nobody in Operations to tell')
        self.assertEqual(told[0]['to'], sorted(everyone))
        self.assertEqual(told[0]['link'], '/approved-items?request=%d' % request_id)
        self.assertIn('Ops probe item', told[0]['body'])


class ExportColumnsTest(_Harness):

    HIDDEN = {'Item ID', 'Type', 'Cost/Unit', 'Total Cost', 'Supplier Email', 'Approval Date'}

    def _header(self, path):
        import openpyxl
        response = self._client_for(1).get(path)
        self.assertEqual(response.status_code, 200, response.data[:200])
        book = openpyxl.load_workbook(io.BytesIO(response.data))
        sheet = book[book.sheetnames[0]]
        return [cell.value for cell in next(sheet.iter_rows(max_row=1))]

    def test_the_six_are_off_by_default_in_every_export(self):
        request_id, _ = self._request_with_item('approved')
        for path in ('/api/operations/approved-items/export/by-request',
                     '/api/operations/approved-items/export/by-supplier',
                     '/api/operations/approved-items/export/request/%d' % request_id):
            with self.subTest(export=path):
                header = self._header(path)
                self.assertFalse(self.HIDDEN & set(header), header)
                self.assertIn('Item Name', header)
                self.assertIn('Supplier', header)

    def test_the_chosen_columns_are_the_columns_in_their_own_order(self):
        request_id, _ = self._request_with_item('approved')
        header = self._header('/api/operations/approved-items/export/request/%d'
                              '?cols=Total Cost,Item Name,Quantity' % request_id)
        self.assertEqual(header, ['Item Name', 'Quantity', 'Total Cost'])

    def test_unknown_or_empty_choices_fall_back_to_the_defaults(self):
        request_id, _ = self._request_with_item('approved')
        base = '/api/operations/approved-items/export/request/%d' % request_id
        default = self._header(base)
        self.assertEqual(self._header(base + '?cols=Nonsense'), default)
        self.assertEqual(self._header(base + '?cols='), default)

    def test_the_chooser_is_told_what_exists_and_what_is_off(self):
        body = self._client_for(1).get('/api/operations/approved-items/export/columns').get_json()
        self.assertEqual(set(body['hidden_by_default']), self.HIDDEN)
        self.assertTrue(self.HIDDEN <= set(body['columns']))


class ExpenseSuppliersTest(_Harness):

    def test_operations_can_read_the_supplier_list(self):
        # Azer's role. This was a 403, and the dropdown said nothing.
        response = self._client_for(self._user_with_role('operations_member')).get('/api/finance/suppliers')
        self.assertEqual(response.status_code, 200, response.data[:200])
        self.assertTrue(response.get_json().get('success'))


class PagesTest(unittest.TestCase):

    def _page(self, name):
        with open(os.path.join(ROOT, 'templates', name), encoding='utf-8') as handle:
            return handle.read()

    def test_the_expense_supplier_defaults_to_transportation_and_other_is_typed(self):
        page = self._page('my_expenses.html')
        self.assertIn('<option value="__transport" selected>Transportation</option>', page)
        self.assertIn("supplierName = 'Transportation';", page)
        # "Other" saves what was typed, and cannot be saved blank.
        self.assertIn("supplierName = ($('#expenseSupplierName').val() || '').trim();", page)
        self.assertIn('for "Other"', page)
        self.assertNotIn('<option value="">Select Supplier</option>', page)

    def test_each_request_has_its_own_colour_in_both_views(self):
        page = self._page('approved_items.html')
        self.assertIn('function requestColor(id)', page)
        self.assertIn("'<div class=\"ai-req\" style=\"' + requestStyle(g.request_id) + '\">'", page)
        self.assertIn("row.setAttribute('style', requestStyle(g.request_id));", page)

    def test_the_table_is_one_row_per_request_that_expands(self):
        page = self._page('approved_items.html')
        self.assertIn('var groups = groupByRequest(allItems);', page)
        self.assertIn("row.child('<div class=\"ai-rq-items\"", page)
        self.assertIn('g.items.map(aiLineHtml)', page)
        self.assertNotIn('rowGroup:', page)

    def test_every_export_carries_the_chosen_columns(self):
        page = self._page('approved_items.html')
        self.assertIn('id="aiColumnsBtn"', page)
        self.assertEqual(page.count('ai-export-link'), 3)       # two links and the handler
        self.assertIn("exportUrl('/api/operations/approved-items/export/request/' + rid)", page)

    def test_the_notice_opens_its_own_request(self):
        page = self._page('approved_items.html')
        self.assertIn("new URLSearchParams(window.location.search).get('request')", page)


if __name__ == '__main__':
    unittest.main()
