"""
Approving a balance request asks which payment method pays it, and there were
none to choose. Finance adds them on Finance Management > Payment Methods; each
is Cash or Bank, and a Bank method must carry its bank name and account number.

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


class PaymentMethodFieldsTest(unittest.TestCase):

    def test_type_is_required(self):
        self.assertIsNotNone(branding_gate.payment_method_fields({})[3])
        self.assertIsNotNone(branding_gate.payment_method_fields({'method_type': 'card'})[3])

    def test_bank_needs_name_and_account(self):
        self.assertIsNotNone(branding_gate.payment_method_fields(
            {'method_type': 'bank', 'bank_name': 'CIB'})[3])
        self.assertEqual(branding_gate.payment_method_fields(
            {'method_type': 'bank', 'bank_name': ' CIB ', 'account_number': '100'}),
            ('bank', 'CIB', '100', None))

    def test_cash_drops_bank_details(self):
        self.assertEqual(branding_gate.payment_method_fields(
            {'method_type': 'cash', 'bank_name': 'CIB', 'account_number': '100'}),
            ('cash', None, None, None))

    def test_edit_keeps_stored_values(self):
        stored = {'method_type': 'bank', 'bank_name': 'NBE', 'account_number': '7'}
        self.assertEqual(branding_gate.payment_method_fields({}, stored), ('bank', 'NBE', '7', None))


class PaymentMethodRoutesTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_RollbackConnection(self.raw),
                                            self.raw.cursor(MySQLdb.cursors.DictCursor))
        branding_gate.app.config['TESTING'] = True
        cur = self.raw.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("""SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
                       WHERE r.code = 'finance_manager' ORDER BY u.id LIMIT 1""")
        row = cur.fetchone()
        cur.close()
        if not row:
            self.skipTest('no finance_manager user')
        perms, role_code = branding_gate.load_permissions(row['id'])
        self.client = branding_gate.app.test_client()
        with self.client.session_transaction() as s:
            s.update({'user_id': row['id'], 'mobile': 'm', 'email': 'e', 'username': 'u',
                      'name': 'Tester', 'user_name': 'Tester',
                      'roles': [role_code], 'perms': perms, 'role_code': role_code})

    def _undo(self):
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _methods(self):
        return {m['method_name']: m for m in
                self.client.get('/api/finance/payment-methods').get_json()['payment_methods']}

    def test_add_cash_and_bank(self):
        r = self.client.post('/api/finance/payment-methods',
                             json={'method_name': 'Test Safe 9x', 'method_type': 'cash'})
        self.assertEqual(r.status_code, 200, r.get_json())
        r = self.client.post('/api/finance/payment-methods',
                             json={'method_name': 'Test Bank 9x', 'method_type': 'bank'})
        self.assertEqual(r.status_code, 400)
        r = self.client.post('/api/finance/payment-methods',
                             json={'method_name': 'Test Bank 9x', 'method_type': 'bank',
                                   'bank_name': 'CIB', 'account_number': '1002003'})
        self.assertEqual(r.status_code, 200, r.get_json())
        got = self._methods()
        self.assertEqual(got['Test Safe 9x']['method_type'], 'cash')
        self.assertEqual(got['Test Safe 9x']['method_code'], 'TEST_SAFE_9X')
        self.assertEqual((got['Test Bank 9x']['method_type'], got['Test Bank 9x']['bank_name'],
                          got['Test Bank 9x']['account_number']), ('bank', 'CIB', '1002003'))

    def test_code_is_generated_and_unique(self):
        for _ in range(2):
            r = self.client.post('/api/finance/payment-methods',
                                 json={'method_name': 'Test Safe 9z', 'method_type': 'cash',
                                       'method_code': 'IGNORED'})
            self.assertEqual(r.status_code, 200, r.get_json())
        cur = self.raw.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT method_code FROM payment_methods WHERE method_name = 'Test Safe 9z' ORDER BY id")
        self.assertEqual([r['method_code'] for r in cur.fetchall()], ['TEST_SAFE_9Z', 'TEST_SAFE_9Z_2'])

    def test_bank_without_label_is_named_after_the_account(self):
        r = self.client.post('/api/finance/payment-methods',
                             json={'method_type': 'bank', 'bank_name': 'QNB9x', 'account_number': '42'})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(self._methods()['QNB9x 42']['bank_name'], 'QNB9x')

    def test_edit_to_bank_requires_details_then_back_to_cash_clears(self):
        mid = self.client.post('/api/finance/payment-methods',
                               json={'method_name': 'Test Safe 9y', 'method_type': 'cash'}).get_json()['id']
        url = '/api/finance/payment-methods/%d' % mid
        self.assertEqual(self.client.put(url, json={'method_type': 'bank'}).status_code, 400)
        self.assertEqual(self.client.put(url, json={'method_type': 'bank', 'bank_name': 'NBE',
                                                    'account_number': '55'}).status_code, 200)
        self.assertEqual(self._methods()['Test Safe 9y']['bank_name'], 'NBE')
        self.assertEqual(self.client.put(url, json={'method_type': 'cash'}).status_code, 200)
        m = self._methods()['Test Safe 9y']
        self.assertEqual((m['method_type'], m['bank_name'], m['account_number']), ('cash', None, None))


if __name__ == '__main__':
    unittest.main()
