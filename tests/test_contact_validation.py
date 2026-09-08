import unittest
from unittest.mock import patch

import MySQLdb
import MySQLdb.cursors
from werkzeug.security import generate_password_hash

import branding_gate


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def close(self): pass
    def rollback(self): pass


class _FirebaseUser:
    uid = '+201555555555'


class ContactValidationTest(unittest.TestCase):
    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self._cursor())
        self.client = branding_gate.app.test_client()
        with self.client.session_transaction() as flask_session:
            flask_session.update({
                "user_id": 1,
                "mobile": "01024527770",
                "email": "owner@example.com",
                "username": "contact-test-admin",
                "name": "Contact Test Admin",
                "roles": ["admin"],
                "role_code": "admin",
                "perms": {
                    "user.create": "all",
                    "client.create": "all",
                    "supplier.create": "all",
                    "company.create": "all",
                    "entity.create": "all",
                    "entity.edit": "all",
                },
            })

    def tearDown(self):
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _one(self, sql, params=()):
        cur = self._cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        cur.close()
        return row

    def test_contact_helpers_normalize_egypt_mobile_numbers_and_emails(self):
        cases = {
            "0 1226401477": "01226401477",
            "+20 122 640 1477": "01226401477",
            "0020-100-200-3000": "01002003000",
            "1002003000": "01002003000",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(branding_gate.normalize_egypt_mobile(raw), expected)
        self.assertEqual(branding_gate.normalize_email("  Person@Example.COM "), "person@example.com")

    def test_contact_helpers_reject_bad_mobile_numbers_and_emails(self):
        for bad in ("01312345678", "010123", "phone", "+20 1312345678"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    branding_gate.normalize_egypt_mobile(bad)
        with self.assertRaises(ValueError):
            branding_gate.normalize_email("person@@example")

    def test_login_normalizes_mobile_before_lookup(self):
        cur = self._cursor()
        cur.execute("""
            INSERT INTO user (name, mobile, email, password, username, title, is_active)
            VALUES ('Login Contact User', '01555555555', 'login-contact@example.com',
                    %s, 'login-contact-user', 'Tester', 1)
        """, (generate_password_hash('123456'),))
        cur.close()

        with patch.object(branding_gate, 'get_user_roles', return_value=['admin']), \
             patch.object(branding_gate, 'load_permissions', return_value=({}, 'admin')), \
             patch.object(branding_gate.auth, 'get_user_by_phone_number', return_value=_FirebaseUser()), \
             patch.object(branding_gate.auth, 'create_custom_token', return_value=b'token'):
            response = self.client.post('/login?add_login=1', data={
                'mobile': '+20 155 555 5555',
                'password': '123456',
            })

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['state'], 'success')

    def test_permission_gate_refreshes_stale_session_before_forbidden(self):
        with self.client.session_transaction() as flask_session:
            flask_session.update({
                "user_id": 400,
                "mobile": "01277583826",
                "email": "gamal@example.com",
                "username": "01277583826",
                "name": "Gamal Gaber",
                "roles": ["account_director"],
                "role_code": "account_director",
                "perms": {"client.edit": "department"},
            })

        response = self.client.post('/api/clients/add', json={
            'client_name': 'Stale Permission Client',
            'mobile_number': '01022223333',
            'email_address': 'stale-permission@example.com',
        })

        self.assertEqual(response.status_code, 200, response.get_json())

    def test_page_render_refreshes_stale_permissions_before_template_gates(self):
        with self.client.session_transaction() as flask_session:
            flask_session.update({
                "user_id": 400,
                "mobile": "01277583826",
                "email": "gamal@example.com",
                "username": "01277583826",
                "name": "Gamal Gaber",
                "roles": ["account_director"],
                "role_code": "account_director",
                "perms": {"client.edit": "department", "portal.account": "all"},
            })

        response = self.client.get('/account')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="quickAddClientModal"', response.data)

    def test_master_data_routes_normalize_contact_fields_before_saving(self):
        response = self.client.post('/api/clients/add', json={
            'client_name': 'Contact Client',
            'mobile_number': '+20 122 640 1477',
            'secondary_mobile_number': '0020 100 200 3000',
            'email_address': ' CLIENT@Example.COM ',
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        row = self._one("SELECT mobile_number, secondary_mobile_number, email_address "
                        "FROM client WHERE client_name='Contact Client'")
        self.assertEqual(row['mobile_number'], '01226401477')
        self.assertEqual(row['secondary_mobile_number'], '01002003000')
        self.assertEqual(row['email_address'], 'client@example.com')

        response = self.client.post('/api/suppliers/add', json={
            'supplier_name': 'Contact Supplier',
            'supplier_type': 'Other',
            'status': 'Active',
            'date_added': '2026-08-25',
            'contact_person_name': 'Supplier Contact',
            'primary_phone': '+20 111 222 3333',
            'secondary_phone': '012 3456 7890',
            'email_address': ' SUPPLIER@Example.COM ',
            'whatsapp_number': '015 5555 5555',
            'preferred_contact_method': 'Phone',
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        row = self._one("SELECT primary_phone, secondary_phone, whatsapp_number, email_address "
                        "FROM supplier WHERE supplier_name='Contact Supplier'")
        self.assertEqual(row['primary_phone'], '01112223333')
        self.assertEqual(row['secondary_phone'], '01234567890')
        self.assertEqual(row['whatsapp_number'], '01555555555')
        self.assertEqual(row['email_address'], 'supplier@example.com')

        response = self.client.post('/api/companies/add', json={
            'company_name': 'Contact Company',
            'industry_sector': 'Health',
            'address': 'Cairo',
            'phone_number': '+20 100 111 2222',
            'email_address': ' COMPANY@Example.COM ',
            'primary_contact_person': 'Company Contact',
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        row = self._one("SELECT phone_number, email_address FROM company "
                        "WHERE company_name='Contact Company'")
        self.assertEqual(row['phone_number'], '01001112222')
        self.assertEqual(row['email_address'], 'company@example.com')

        response = self.client.post('/api/users/add', json={
            'name': 'Contact User',
            'mobile': '+20 155 555 5555',
            'email': ' USER@Example.COM ',
            'password': '123456',
            'username': 'contact-user',
            'title': 'Tester',
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        row = self._one("SELECT mobile, email FROM user WHERE username='contact-user'")
        self.assertEqual(row['mobile'], '01555555555')
        self.assertEqual(row['email'], 'user@example.com')

        response = self.client.post('/api/entities', json={
            'entity_name': 'Contact Entity',
            'entity_code': 'ce1',
            'contact_phone': '+20 120 000 0000',
            'contact_email': ' ENTITY@Example.COM ',
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        row = self._one("SELECT id, contact_phone, contact_email FROM entities "
                        "WHERE entity_code='CE1'")
        self.assertEqual(row['contact_phone'], '01200000000')
        self.assertEqual(row['contact_email'], 'entity@example.com')

        response = self.client.put('/api/entities/%s' % row['id'], json={
            'entity_name': 'Contact Entity',
            'entity_code': 'ce1',
            'contact_phone': '010 9999 9999',
            'contact_email': ' UPDATED@Example.COM ',
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        row = self._one("SELECT contact_phone, contact_email FROM entities WHERE entity_code='CE1'")
        self.assertEqual(row['contact_phone'], '01099999999')
        self.assertEqual(row['contact_email'], 'updated@example.com')

    def test_routes_reject_invalid_contact_fields(self):
        response = self.client.post('/api/clients/add', json={
            'client_name': 'Bad Client',
            'mobile_number': '01312345678',
            'email_address': 'client@example.com',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('Egyptian mobile', response.get_json()['error'])

        response = self.client.post('/api/suppliers/add', json={
            'supplier_name': 'Bad Supplier',
            'supplier_type': 'Other',
            'status': 'Active',
            'date_added': '2026-08-25',
            'contact_person_name': 'Supplier Contact',
            'primary_phone': '01012345678',
            'email_address': 'bad-email',
            'preferred_contact_method': 'Phone',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('valid email', response.get_json()['error'])


if __name__ == '__main__':
    unittest.main()
