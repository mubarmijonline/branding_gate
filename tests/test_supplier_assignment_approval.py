"""
Supplier assignment through Finance (Ahmed, 2026-11-11).

Putting an item with a supplier makes its cost owed to them, so Operations (the
head or a team leader) asks with documents and Finance approves before the item
changes. The item's costing is the agreed cost; the actual cost may differ, and
above agreed the Operations head approves first. Every Finance approval can be
decided from its notification. Rolled back.
"""

import testdb  # noqa: F401  first: the test database, not the live one
import io
import tempfile
import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate
import fixtures


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def close(self): pass
    def rollback(self): pass


class SupplierAssignmentApprovalTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db=testdb.DB, charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = (branding_gate.connection, branding_gate.notify_users, branding_gate.notify_user,
                         branding_gate.SUPPLIER_ASSIGNMENT_FILES_DIR)
        self.told = []
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self._cursor())
        branding_gate.notify_users = lambda users, title, content, link=None, category=None, action=None: \
            self.told.append((title, action))
        branding_gate.notify_user = lambda *a, **k: None
        branding_gate.SUPPLIER_ASSIGNMENT_FILES_DIR = tempfile.mkdtemp()
        self.addCleanup(self._undo)
        cur = self._cursor()
        ids = {}
        for code in ('operations_manager', 'operations_team_leader', 'operations_member', 'finance_manager'):
            cur.execute("SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id "
                        "WHERE r.code = %s AND u.is_active = 1 ORDER BY u.id LIMIT 1", (code,))
            row = cur.fetchone()
            ids[code] = row and row['id']
        self.head, self.leader, self.member, self.finance = (ids['operations_manager'], ids['operations_team_leader'],
                                                             ids['operations_member'], ids['finance_manager'])
        if not (self.head and self.leader and self.finance):
            self.skipTest('needs an operations head, a team leader and a finance manager')
        client_id = fixtures.ensure_client(cur)
        cur.execute("INSERT INTO sales_request (client_id, title, start_date, created_by, owner_user_id) "
                    "VALUES (%s, 'SA test', CURDATE(), 'test', %s)", (client_id, self.head))
        self.request_id = cur.lastrowid
        cur.execute("""INSERT INTO sales_request_items (request_id, name, qty, cost_per_item, total_cost, approval_status)
                       VALUES (%s, 'Stage', 1, 15000, 15000, 'approved')""", (self.request_id,))
        self.item_id = cur.lastrowid
        self.supplier = fixtures.ensure_suppliers(cur, 1)[0]

    def _undo(self):
        (branding_gate.connection, branding_gate.notify_users, branding_gate.notify_user,
         branding_gate.SUPPLIER_ASSIGNMENT_FILES_DIR) = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _web(self, user_id):
        perms, role = branding_gate.load_permissions(user_id)
        web = branding_gate.app.test_client()
        with web.session_transaction() as s:
            s.update({'user_id': user_id, 'mobile': 'm', 'email': 'e', 'username': 'u', 'name': 'T',
                      'roles': [role], 'perms': perms, 'role_code': role})
        return web

    def _ask(self, actor, actual=None, files=True, note=''):
        data = {'supplier_id': str(self.supplier), 'due_date': '2026-12-01', 'note': note}
        if actual is not None:
            data['actual_cost'] = str(actual)
        if files:
            data['files'] = (io.BytesIO(b'%PDF-1.4'), 'quote.pdf')
        return self._web(actor).post('/api/approved-items/%d/supplier-request' % self.item_id,
                                     data=data, content_type='multipart/form-data')

    def _item(self):
        cur = self._cursor()
        cur.execute("SELECT supplier_id, supplier_cost FROM sales_request_items WHERE id = %s", (self.item_id,))
        return cur.fetchone()

    def test_the_supplier_changes_only_through_finance(self):
        r = self._web(self.leader).put('/api/approved-items/%d/supplier' % self.item_id,
                                       json={'supplier_id': self.supplier})
        self.assertEqual(r.status_code, 400)
        self.assertTrue(r.get_json()['needs_finance'])
        self.assertEqual(self._ask(self.leader, files=False).status_code, 400)        # a document is required
        r = self._ask(self.leader)
        self.assertEqual(r.status_code, 200, r.get_json())
        assignment = r.get_json()['assignment_id']
        self.assertIsNone(self._item()['supplier_id'])                               # nothing until Finance
        self.assertEqual(self.told[-1][1], {'kind': 'supplier_assignment', 'id': assignment, 'stage': 'finance'})
        self.assertEqual(self._ask(self.leader).status_code, 400)                    # one request at a time
        r = self._web(self.finance).post('/api/finance/supplier-assignments/%d/approve' % assignment, json={})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual((self._item()['supplier_id'], float(self._item()['supplier_cost'])), (self.supplier, 15000.0))

    def test_only_the_head_and_team_leaders_assign(self):
        if not self.member:
            self.skipTest('no operations member')
        self.assertEqual(self._ask(self.member).status_code, 403)

    def test_a_lower_actual_cost_goes_straight_to_finance_and_is_what_is_owed(self):
        r = self._ask(self.leader, actual=12000)
        self.assertEqual(r.get_json()['status'], 'pending')
        self._web(self.finance).post('/api/finance/supplier-assignments/%d/approve' % r.get_json()['assignment_id'], json={})
        owed = branding_gate.supplier_purchases_by_request(self._cursor(), self.supplier, self.request_id)[0]
        self.assertEqual(owed['purchased'], 12000.0)

    def test_above_agreed_waits_for_the_head_then_finance(self):
        self.assertEqual(self._ask(self.leader, actual=17000).status_code, 400)       # needs a reason
        r = self._ask(self.leader, actual=17000, note='Rush delivery')
        self.assertEqual(r.get_json()['status'], 'pending_head')
        assignment = r.get_json()['assignment_id']
        self.assertEqual(self.told[-1][1]['stage'], 'head')
        finance = self._web(self.finance)
        self.assertEqual(finance.post('/api/finance/supplier-assignments/%d/approve' % assignment, json={}).status_code, 400)
        head = self._web(self.head)
        listed = head.get('/api/supplier-assignments/over-agreed').get_json()['requests']
        self.assertIn(assignment, [x['id'] for x in listed])
        self.assertEqual(head.get('/api/approvals/waiting-counts').get_json()['counts']['supplier_cost'] >= 1, True)
        self.assertEqual(head.post('/api/supplier-assignments/%d/head-approve' % assignment, json={}).status_code, 200)
        self.assertEqual(self.told[-1][1]['stage'], 'finance')
        self.assertEqual(finance.post('/api/finance/supplier-assignments/%d/approve' % assignment, json={}).status_code, 200)
        self.assertEqual(float(self._item()['supplier_cost']), 17000.0)

    def test_the_heads_own_request_above_agreed_goes_to_finance(self):
        r = self._ask(self.head, actual=16000, note='Agreed with the client')
        self.assertEqual(r.get_json()['status'], 'pending')

    def test_finance_decides_from_the_notification(self):
        assignment = self._ask(self.leader).get_json()['assignment_id']
        d = self._web(self.finance).get('/api/quick-approvals/supplier_assignment/%d?stage=finance' % assignment).get_json()
        self.assertTrue(d['quick'], d)
        self.assertEqual(len(d['attachments']), 1)
        self.assertTrue(d['approve_url'].endswith('/approve'))
        self.assertEqual(self._web(self.finance).post(d['reject_url'], json={'reason': ''}).status_code, 400)
        self.assertEqual(self._web(self.finance).post(d['reject_url'], json={'reason': 'Wrong supplier'}).status_code, 200)
        self.assertIsNone(self._item()['supplier_id'])


class FinanceQuickApprovalsTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db=testdb.DB, charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = (branding_gate.connection, branding_gate.notify_users)
        self.told = []
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self.raw.cursor(MySQLdb.cursors.DictCursor))
        branding_gate.notify_users = lambda users, title, content, link=None, category=None, action=None: \
            self.told.append(action)
        self.addCleanup(self._undo)
        self.cur = self.raw.cursor(MySQLdb.cursors.DictCursor)
        self.cur.execute("SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id "
                         "WHERE r.code = 'finance_manager' AND u.is_active = 1 LIMIT 1")
        self.finance = self.cur.fetchone()['id']

    def _undo(self):
        branding_gate.connection, branding_gate.notify_users = self.original
        self.raw.rollback()
        self.raw.close()

    def _web(self):
        perms, role = branding_gate.load_permissions(self.finance)
        web = branding_gate.app.test_client()
        with web.session_transaction() as s:
            s.update({'user_id': self.finance, 'mobile': 'm', 'email': 'e', 'username': 'u', 'name': 'T',
                      'roles': [role], 'perms': perms, 'role_code': role})
        return web

    def test_a_my_expenses_line_is_decided_with_its_receipt_and_account(self):
        self.cur.execute("SELECT id FROM user WHERE is_active = 1 ORDER BY id LIMIT 1")
        owner = self.cur.fetchone()['id']
        self.cur.execute("""INSERT INTO user_expense_tracking (user_id, tracking_code, supplier_name, amount, description,
                               expense_date, status) VALUES (%s, 'EXP-QA1', 'Transportation', 120, 'Taxi', CURDATE(), 'submitted')""",
                         (owner,))
        line = self.cur.lastrowid
        self.cur.execute("INSERT INTO expense_attachments (expense_id, stored_path, original_name, file_type) "
                         "VALUES (%s, '/nowhere/r.jpg', 'r.jpg', 'image/jpeg')", (line,))
        branding_gate.notify_finance_of_expenses(self.cur, [line], 'Manager')
        self.assertEqual(self.told[-1], {'kind': 'my_expense', 'id': line, 'stage': 'finance'})
        d = self._web().get('/api/quick-approvals/my_expense/%d?stage=finance' % line).get_json()
        self.assertTrue(d['quick'])
        self.assertEqual([i['name'] for i in d['inputs']], ['payment_method_id', 'category_id'])
        transport = [i for i in d['inputs'] if i['name'] == 'category_id'][0]['value']
        self.assertIsNotNone(transport)                                   # 6212 picked for Transportation
        self.assertEqual(d['attachments'][0]['name'], 'r.jpg')
        pm = d['inputs'][0]['options'][0]['value']
        body = {'payment_method_id': pm, 'expenses': [{'id': line, 'amount': 120, 'category_id': transport}]}
        r = self._web().post(d['approve_url'], json=body)
        self.assertEqual(r.get_json()['approved_count'], 1, r.get_json())

    def test_custody_and_pending_transactions_carry_what_finance_needs(self):
        self.cur.execute("SELECT id FROM user_balance_transfers ORDER BY id DESC LIMIT 1")
        row = self.cur.fetchone()
        if row:
            d = branding_gate._quick_details(self.cur, 'custody', row['id'], 'finance')
            self.assertEqual(d['inputs'][0]['name'], 'payment_method_id')
            self.assertEqual(d['approve_body']['payment_method_id'], '$payment_method_id')
        self.cur.execute("SELECT id FROM finance_transactions ORDER BY id DESC LIMIT 1")
        txn = self.cur.fetchone()['id']
        d = branding_gate._quick_details(self.cur, 'finance_txn', txn, None)
        self.assertTrue(d['approve_url'].endswith('/approve'))


if __name__ == '__main__':
    unittest.main()
