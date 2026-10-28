"""
Design requests (WhatsApp request #1, Gamal Gaber).

The policy half (design_requests.py) and the grants need no database. The
route half is exercised through the Flask test client against a scripted
cursor that answers each query by what it is asking, with notify_users
captured, so the hand-offs and their links are pinned without MySQL.
"""

import datetime
import unittest
from unittest import mock

import branding_gate
import design_requests as dr
import rbac


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

class CategoryFieldsTest(unittest.TestCase):
    """The seven tabs and what each one carries, as the spec draws them."""

    def test_the_seven_categories_in_spec_order(self):
        self.assertEqual(dr.CATEGORY_CODES, (
            'social_media', 'printing_production', 'video', 'mockup_reference',
            'identity', 'presentation', 'other'))

    def test_printing_carries_size_quantity_and_type(self):
        self.assertEqual(dr.CATEGORY_FIELDS['printing_production'],
                         ('size_h', 'size_w', 'size_l', 'quantity', 'printing_type'))

    def test_video_carries_h_w_and_duration(self):
        self.assertEqual(dr.CATEGORY_FIELDS['video'], ('size_h', 'size_w', 'duration'))

    def test_other_carries_the_union(self):
        self.assertEqual(set(dr.CATEGORY_FIELDS['other']),
                         {'size_h', 'size_w', 'size_l', 'quantity', 'printing_type', 'duration'})

    def test_the_plain_categories_carry_only_the_shared_fields(self):
        for code in ('social_media', 'mockup_reference', 'identity', 'presentation'):
            self.assertEqual(dr.CATEGORY_FIELDS[code], (), code)

    def test_a_social_media_item_cannot_grow_a_quantity(self):
        item = dr.clean_item({'category': 'social_media', 'title': 'Post', 'quantity': '5',
                              'size_h': '10', 'printing_type': 'Vinyl'})
        self.assertIsNone(item['quantity'])
        self.assertIsNone(item['size_h'])
        self.assertIsNone(item['printing_type'])

    def test_a_printing_item_keeps_its_fields_and_stores_the_word(self):
        item = dr.clean_item({'category': 'printing_production', 'title': 'Roll-up',
                              'size_h': '200', 'size_w': '85', 'size_l': '0', 'quantity': '3',
                              'printing_type': 'Vinyl', 'duration': '30s'})
        self.assertEqual((item['size_h'], item['size_w'], item['size_l']),
                         (dr.Decimal('200'), dr.Decimal('85'), dr.Decimal('0')))
        self.assertEqual(item['quantity'], 3)
        self.assertEqual(item['printing_type'], 'Vinyl')
        self.assertIsNone(item['duration'])

    def test_quantity_is_whole_units(self):
        with self.assertRaises(dr.DesignRequestError):
            dr.clean_item({'category': 'printing_production', 'title': 'x', 'quantity': '2.5'})

    def test_a_typed_printing_type_is_kept_as_typed(self):
        item = dr.clean_item({'category': 'other', 'title': 'x', 'printing_type': 'Sublimation'})
        self.assertEqual(item['printing_type'], 'Sublimation')
        self.assertIn('Vinyl', dr.PRINTING_TYPES)

    def test_every_item_needs_a_category_and_a_title(self):
        with self.assertRaises(dr.DesignRequestError):
            dr.clean_item({'title': 'x'})
        with self.assertRaises(dr.DesignRequestError):
            dr.clean_item({'category': 'video'})

    def test_the_header_needs_a_company_or_a_client(self):
        with self.assertRaises(dr.DesignRequestError):
            dr.clean_header({'deadline': '2026-11-01'})
        header = dr.clean_header({'client_id': '4', 'deadline': '2026-11-01'})
        self.assertEqual(header['client_id'], 4)
        self.assertEqual(header['designer_kind'], '2d')
        self.assertEqual(dr.clean_header({'company_id': 2, 'designer_kind': '3d'})['designer_kind'], '3d')
        with self.assertRaises(dr.DesignRequestError):
            dr.clean_header({'company_id': 2, 'designer_kind': 'vr'})


class WorkflowTest(unittest.TestCase):
    """submitted -> assigned -> delivered -> approved | rejected -> sent to Operation."""

    def test_assign_wants_a_designer_from_the_same_team(self):
        self.assertEqual(dr.check_assign(dr.SUBMITTED, '2d', '2d'), 'assigned')
        self.assertEqual(dr.check_assign(dr.ASSIGNED, '2d', '2d'), 'reassigned')
        with self.assertRaises(dr.DesignRequestError):
            dr.check_assign(dr.SUBMITTED, '3d', '2d')
        with self.assertRaises(dr.DesignRequestError):
            dr.check_assign(dr.SUBMITTED, None, '2d')

    def test_an_approved_request_is_not_reassigned(self):
        for status in (dr.APPROVED, dr.SENT_TO_OPERATION):
            with self.assertRaises(dr.DesignRequestError):
                dr.check_assign(status, '2d', '2d')

    def test_only_the_assigned_designer_delivers_and_only_while_it_is_with_them(self):
        self.assertTrue(dr.check_deliver(dr.ASSIGNED, 9, 9))
        self.assertTrue(dr.check_deliver(dr.REJECTED, 9, 9))
        with self.assertRaises(dr.DesignRequestError):
            dr.check_deliver(dr.ASSIGNED, 8, 9)
        with self.assertRaises(dr.DesignRequestError):
            dr.check_deliver(dr.SUBMITTED, 9, 9)
        with self.assertRaises(dr.DesignRequestError):
            dr.check_deliver(dr.DELIVERED, 9, 9)

    def test_a_decision_needs_a_delivery(self):
        self.assertEqual(dr.check_decide(dr.DELIVERED, 'approve'), dr.APPROVED)
        self.assertEqual(dr.check_decide(dr.DELIVERED, 'reject'), dr.REJECTED)
        with self.assertRaises(dr.DesignRequestError):
            dr.check_decide(dr.ASSIGNED, 'approve')
        with self.assertRaises(dr.DesignRequestError):
            dr.check_decide(dr.DELIVERED, 'maybe')

    def test_the_requester_sends_an_approved_design_to_operation(self):
        self.assertTrue(dr.check_send_to_operation(dr.APPROVED, 3, 3))
        with self.assertRaises(dr.DesignRequestError):
            dr.check_send_to_operation(dr.APPROVED, 4, 3)
        self.assertTrue(dr.check_send_to_operation(dr.APPROVED, 4, 3, unrestricted=True))
        with self.assertRaises(dr.DesignRequestError):
            dr.check_send_to_operation(dr.DELIVERED, 3, 3)

    def test_a_deliverable_is_pdf_jpg_png_or_a_link(self):
        self.assertEqual(dr.deliverable_ok('final.PDF'), 'file')
        self.assertEqual(dr.deliverable_ok('final.png'), 'file')
        self.assertEqual(dr.deliverable_ok(None, 'https://drive.google.com/x'), 'link')
        with self.assertRaises(dr.DesignRequestError):
            dr.deliverable_ok('final.psd')
        with self.assertRaises(dr.DesignRequestError):
            dr.deliverable_ok(None, 'drive.google.com/x')
        with self.assertRaises(dr.DesignRequestError):
            dr.deliverable_ok(None, None)

    def test_each_kind_has_its_own_portal(self):
        self.assertEqual(dr.portal_for('2d'), '/design-2d')
        self.assertEqual(dr.portal_for('3d'), '/design-3d')


# ---------------------------------------------------------------------------
# Grants
# ---------------------------------------------------------------------------

DESIGN_PERMS = ('design_request.view', 'design_request.create', 'design_request.assign',
                'design_request.deliver', 'design_request.approve', 'design_request.send_operation')


class GrantsTest(unittest.TestCase):

    def test_the_six_permissions_exist(self):
        for code in DESIGN_PERMS:
            self.assertIn(code, rbac.PERMISSIONS)
            self.assertEqual(rbac.SEED_MATRIX['admin'][code], 'all')

    def test_approval_is_the_design_heads_not_the_account_director(self):
        holders = {role for role, grants in rbac.SEED_MATRIX.items()
                   if 'design_request.approve' in grants}
        self.assertEqual(holders, {'admin', 'design_2d_head', 'design_3d_head', 'design_3d_purchasing'})
        self.assertNotIn('design_request.approve', rbac.SEED_MATRIX['account_director'])
        self.assertNotIn('design_request.assign', rbac.SEED_MATRIX['account_director'])

    def test_the_requesting_lines_raise_and_send_on_at_own_scope(self):
        for role in ('sales_member', 'sales_team_leader', 'sales_head',
                     'account_member', 'account_team_leader', 'account_director',
                     'marketing_member', 'digital_marketing_team_leader', 'marketing_manager'):
            self.assertEqual(rbac.SEED_MATRIX[role]['design_request.create'], 'own', role)
            self.assertEqual(rbac.SEED_MATRIX[role]['design_request.send_operation'], 'own', role)
            self.assertIn('design_request.view', rbac.SEED_MATRIX[role], role)

    def test_viewing_widens_by_level_like_sales_requests(self):
        self.assertEqual(rbac.SEED_MATRIX['sales_member']['design_request.view'], 'own')
        self.assertEqual(rbac.SEED_MATRIX['sales_team_leader']['design_request.view'], 'team')
        self.assertEqual(rbac.SEED_MATRIX['account_director']['design_request.view'], 'department')

    def test_designers_deliver_what_is_on_their_desk_and_nothing_else(self):
        for role in ('design_2d_member', 'design_3d_member'):
            grants = rbac.SEED_MATRIX[role]
            self.assertEqual(grants['design_request.deliver'], 'own', role)
            self.assertEqual(grants['design_request.view'], 'own', role)
            for code in ('design_request.create', 'design_request.assign',
                         'design_request.approve', 'design_request.send_operation'):
                self.assertNotIn(code, grants, '%s / %s' % (role, code))

    def test_the_operations_head_sees_what_is_handed_over(self):
        self.assertEqual(rbac.SEED_MATRIX['operations_manager']['design_request.view'], 'all')
        self.assertNotIn('design_request.view', rbac.SEED_MATRIX['operations_member'])

    def test_the_routes_are_gated_on_the_right_permission(self):
        wanted = {
            'design_requests_page': ('design_request.view',),
            'design_requests_list': ('design_request.view',),
            'design_request_detail': ('design_request.view',),
            'design_request_create': ('design_request.create',),
            'design_request_designers': ('design_request.assign',),
            'design_request_assign': ('design_request.assign',),
            'design_request_deliver': ('design_request.deliver',),
            'design_request_decide': ('design_request.approve',),
            'design_request_send_to_operation': ('design_request.send_operation',),
            'design_2d_portal': ('portal.design_2d',),
            'design_3d_portal': ('portal.design_3d',),
        }
        for endpoint, perms in wanted.items():
            view = branding_gate.app.view_functions[endpoint]
            self.assertEqual(tuple(view._perms), perms, endpoint)

    def test_the_design_portals_render_the_queue_not_the_placeholder(self):
        import inspect
        for endpoint in ('design_2d_portal', 'design_3d_portal'):
            source = inspect.getsource(branding_gate.app.view_functions[endpoint])
            self.assertIn('_design_portal', source)
        for endpoint in ('marketing_portal', 'account_portal'):
            source = inspect.getsource(branding_gate.app.view_functions[endpoint])
            self.assertIn('_blank_portal', source)

    def test_hand_off_titles_are_important(self):
        for title in ('New design request #4 to assign', 'Design request #4 assigned to you',
                      'Design delivered: request #4 to approve',
                      'Design approved: request #4, send it to Operation',
                      'Design sent back: request #4', 'Design for Operation: request #4'):
            self.assertEqual(branding_gate.notification_category(title), 'important', title)
        self.assertEqual(branding_gate.notification_category('Design request #4 delivered'),
                         'announcement')


# ---------------------------------------------------------------------------
# Routes, against a scripted cursor
# ---------------------------------------------------------------------------

NOW = datetime.datetime(2026, 10, 28, 14, 0)


def a_request(**over):
    row = {
        'id': 4, 'designer_kind': '2d', 'company_id': 2, 'client_id': 3,
        'event_date': datetime.date(2026, 12, 1), 'deadline': datetime.date(2026, 11, 20),
        'notes': None, 'status': dr.SUBMITTED, 'owner_user_id': 30, 'assignee_id': None,
        'assigned_by': None, 'assigned_at': None, 'delivered_at': None, 'delivery_note': None,
        'decided_by': None, 'decided_at': None, 'decision_note': None,
        'sent_to_operation_by': None, 'sent_to_operation_at': None,
        'added_date': NOW, 'modified_date': NOW,
        'company_name': 'Acme', 'client_name': 'Mona', 'owner_name': 'Sara (Account)',
        'assignee_name': None, 'decided_by_name': None,
    }
    row.update(over)
    return row


class ScriptedCursor:
    """
    Answers each query from a list of (substring, rows). The first entry whose
    substring is in the SQL wins and is consumed; everything else answers
    nothing. Writes are recorded.
    """

    def __init__(self, answers):
        self.answers = list(answers)
        self.executed = []
        self._result = []
        self.lastrowid = 77

    def execute(self, sql, params=None):
        self.executed.append((' '.join(sql.split()), params))
        self._result = []
        for index, (needle, rows) in enumerate(self.answers):
            if needle in sql:
                self._result = list(rows)
                del self.answers[index]
                break

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result)

    def close(self):
        pass


class ScriptedConnection:
    def __init__(self):
        self.committed = False

    def commit(self):
        self.committed = True

    def close(self):
        pass

    def rollback(self):
        pass


class RouteTest(unittest.TestCase):

    def setUp(self):
        self.original = branding_gate.connection
        self.addCleanup(lambda: setattr(branding_gate, 'connection', self.original))
        branding_gate.app.config['TESTING'] = True
        self.sent = []
        patcher = mock.patch.object(branding_gate, 'notify_users',
                                    lambda ids, title, content, link=None, **kw:
                                    self.sent.append((sorted(int(i) for i in ids), title, link)) or len(ids))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _script(self, *answers):
        self.cursor = ScriptedCursor(answers)
        self.conn = ScriptedConnection()
        branding_gate.connection = lambda: (self.conn, self.cursor)

    def _client(self, user_id, role):
        client = branding_gate.app.test_client()
        with client.session_transaction() as s:
            s.update({'user_id': user_id, 'mobile': 'm', 'email': 'e', 'username': 'u',
                      'name': 'Tester', 'roles': [role], 'role_code': role,
                      'perms': rbac.SEED_MATRIX[role],
                      'perms_loaded_at': datetime.datetime.now().isoformat()})
        return client

    def test_a_designer_cannot_approve_and_a_requester_cannot_assign(self):
        self._script()
        self.assertEqual(self._client(9, 'design_2d_member').post(
            '/api/design-requests/4/decide', json={'decision': 'approve'}).status_code, 403)
        self.assertEqual(self._client(30, 'account_member').post(
            '/api/design-requests/4/assign', json={'assignee_id': 9}).status_code, 403)
        self.assertEqual(self._client(30, 'account_director').post(
            '/api/design-requests/4/decide', json={'decision': 'approve'}).status_code, 403)

    def test_sending_back_without_a_reason_is_refused_before_anything_is_written(self):
        self._script()
        response = self._client(5, 'design_2d_head').post(
            '/api/design-requests/4/decide', json={'decision': 'reject', 'note': ''})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.cursor.executed, [])

    def test_a_delivery_needs_a_file_or_a_link(self):
        self._script()
        response = self._client(9, 'design_2d_member').post(
            '/api/design-requests/4/deliver', data={'note': 'done'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('PDF, JPG or PNG', response.get_json()['error'])

    def test_creating_needs_an_item(self):
        self._script()
        response = self._client(30, 'account_member').post(
            '/api/design-requests', data={'client_id': '3', 'items': '[]'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('at least one item', response.get_json()['error'])

    def test_approving_tells_the_requester_to_send_it_on_and_the_designer_it_passed(self):
        self._script(
            ('SELECT d.code FROM user u', [{'code': 'design_2d'}]),   # the viewer's team
            ('FROM design_request r', [a_request(status=dr.DELIVERED, assignee_id=9,
                                                 assignee_name='Mayar')]),
        )
        response = self._client(5, 'design_2d_head').post(
            '/api/design-requests/4/decide', json={'decision': 'approve', 'note': 'nice'})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['status'], dr.APPROVED)
        self.assertTrue(self.conn.committed)
        updates = [sql for sql, _ in self.cursor.executed if sql.startswith('UPDATE design_request')]
        self.assertEqual(len(updates), 1)
        logged = [p for sql, p in self.cursor.executed if 'INSERT INTO design_request_log' in sql]
        self.assertEqual(logged[0][2], 'approved')
        self.assertEqual(self.sent, [
            ([30], 'Design approved: request #4, send it to Operation', '/design_requests?request=4'),
            ([9], 'Design request #4 approved', '/design-2d?request=4'),
        ])

    def test_a_3d_head_cannot_decide_a_2d_request(self):
        self._script(
            ('SELECT d.code FROM user u', [{'code': 'design_3d'}]),
            ('FROM design_request r', [a_request(status=dr.DELIVERED, assignee_id=9)]),
        )
        response = self._client(6, 'design_3d_head').post(
            '/api/design-requests/4/decide', json={'decision': 'approve'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.conn.committed)

    def test_sending_to_operation_notifies_the_operations_head_with_a_link(self):
        self._script(
            ('FROM design_request r', [a_request(status=dr.APPROVED, assignee_id=9)]),
            ("d.code = 'operations'", [{'id': 12}, {'id': 13}]),
        )
        response = self._client(30, 'account_member').post(
            '/api/design-requests/4/send-to-operation', json={'note': 'print by Monday'})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['status'], dr.SENT_TO_OPERATION)
        self.assertEqual(response.get_json()['told'], 2)
        update = [p for sql, p in self.cursor.executed if sql.startswith('UPDATE design_request')][0]
        self.assertEqual(update[0], dr.SENT_TO_OPERATION)
        self.assertEqual(self.sent[0], ([12, 13], 'Design for Operation: request #4',
                                        '/design_requests?request=4'))

    def test_somebody_elses_approved_request_cannot_be_sent_by_a_colleague(self):
        self._script(('FROM design_request r', [a_request(status=dr.APPROVED, owner_user_id=31)]))
        # own scope: a colleague's request is outside what this member may even see.
        response = self._client(30, 'account_member').post(
            '/api/design-requests/4/send-to-operation', json={})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.sent, [])

    def test_assigning_checks_the_designers_team(self):
        self._script(
            ('FROM design_request r', [a_request()]),
            ('d.code AS department_code', [{'id': 9, 'name': 'Mayar', 'department_code': 'design_3d'}]),
        )
        response = self._client(5, 'design_2d_head').post(
            '/api/design-requests/4/assign', json={'assignee_id': 9})
        self.assertEqual(response.status_code, 403)
        self.assertIn('2D team', response.get_json()['error'])
        self.assertFalse(self.conn.committed)

    def test_assigning_tells_the_designer_and_the_requester(self):
        self._script(
            ('FROM design_request r', [a_request()]),
            ('d.code AS department_code', [{'id': 9, 'name': 'Mayar', 'department_code': 'design_2d'}]),
        )
        response = self._client(5, 'design_2d_head').post(
            '/api/design-requests/4/assign', json={'assignee_id': 9, 'note': 'urgent'})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertTrue(self.conn.committed)
        self.assertEqual([s[:2] for s in self.sent], [
            ([9], 'Design request #4 assigned to you'),
            ([30], 'Design request #4 is with Mayar'),
        ])
        self.assertEqual(self.sent[0][2], '/design-2d?request=4')

    def test_the_requester_page_and_the_portals_say_so(self):
        self._script()
        page = self._client(30, 'account_member').get('/design_requests')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'New design request', page.data)
        self.assertIn(b'Show all requests', page.data)
        self._script(('SELECT d.code FROM user u', [{'code': 'design_2d'}]))
        portal = self._client(5, 'design_2d_head').get('/design-2d')
        self.assertEqual(portal.status_code, 200)
        self.assertIn(b'Design requests for the 2D Design team', portal.data)
        self.assertNotIn(b'New design request', portal.data)   # the head does not raise them
        self.assertEqual(self._client(5, 'design_2d_head').get('/design-3d').status_code, 403)


if __name__ == '__main__':
    unittest.main()
