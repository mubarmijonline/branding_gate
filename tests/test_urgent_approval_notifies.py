"""
Approving an urgent-date request creates it, and Operations is told exactly as
for any new request; the requester is told by name, with a link. Rollback-based.
"""

import json
import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass


class UrgentApprovalNotifiesTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = (branding_gate.connection, branding_gate.send_notification_to_role, branding_gate.notify_user)
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self.raw.cursor(MySQLdb.cursors.DictCursor))
        self.sent = []
        branding_gate.send_notification_to_role = lambda role, title, content, link=None: self.sent.append((role, title, link)) or 1
        branding_gate.notify_user = lambda uid, title, content, link=None, **_: self.sent.append((uid, title, link)) or 1
        branding_gate.app.config['TESTING'] = True
        cur = self.raw.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT id, mobile FROM user WHERE id = 107397")
        self.requester = cur.fetchone()
        cur.execute("SELECT id, client_id, company_id FROM sales_request ORDER BY id LIMIT 1")
        sr = cur.fetchone()
        data = {'title': 'Urgent test', 'client_id': sr['client_id'], 'company_id': sr['company_id'], 'priority': 'high',
                'start_date': '2026-10-29', 'end_date': None, 'request_type': 'Printing', 'request_types': ['Printing'],
                'duration_days': 1, 'template_code': None, 'template_fields': {'instances': [], 'flat_fields': {}}}
        cur.execute("""INSERT INTO sales_request_approvals (request_type, request_data, requested_by, approval_reason)
                       VALUES ('sales_request', %s, %s, 'Urgent date')""", (json.dumps(data), self.requester['mobile']))
        self.approval = cur.lastrowid
        perms, role = branding_gate.load_permissions(1)
        self.web = branding_gate.app.test_client()
        with self.web.session_transaction() as s:
            s.update({'user_id': 1, 'mobile': 'm', 'email': 'e', 'username': '01024527770', 'name': 'Ahmed DiaB',
                      'roles': [role], 'perms': perms, 'role_code': role})

    def _undo(self):
        branding_gate.connection, branding_gate.send_notification_to_role, branding_gate.notify_user = self.original
        self.raw.rollback()
        self.raw.close()

    def test_operations_and_requester_are_told(self):
        r = self.web.post('/api/approvals/%d/approve' % self.approval, json={})
        self.assertEqual(r.status_code, 200, r.get_json())
        new_id = r.get_json()['sales_request_id']
        self.assertIn(('operation', 'New Sales Request #%06d' % new_id, '/operation_request?request=%d' % new_id), self.sent)
        self.assertIn((self.requester['id'], 'Request Approved', '/sales_request?request=%d' % new_id), self.sent)


if __name__ == '__main__':
    unittest.main()
