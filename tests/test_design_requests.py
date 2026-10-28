"""
Design requests (docs/PRD.md "Design Requests"): the requester asks, a design
head assigns, the designer uploads and submits, the Design Manager approves,
the requester sends it to Operation. Each step refused to the wrong person.
Rolled back like test_costing.py; notify_users is off under unittest.
"""

import io
import json
import shutil
import tempfile
import unittest

import branding_gate
import design_workflow
from test_costing import _CostingHarness
import fixtures


class DesignRequestTest(_CostingHarness):

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        for code in ('account_member', 'account_director', 'design_2d_head', 'design_2d_member',
                     'design_manager', 'design_3d_member'):
            cur.execute("SELECT id FROM rbac_role WHERE code = %s", (code,))
            self.roles[code] = cur.fetchone()['id']
        cur.close()
        self.director = self._in('account', self._make_user('dr-director', 'account_director', None))
        self.requester = self._in('account', self._make_user('dr-requester', 'account_member', self.director))
        self.other_requester = self._in('account', self._make_user('dr-other', 'account_member', None))
        self.design_head = self._in('design_2d', self._make_user('dr-head', 'design_2d_head', None))
        self.designer = self._in('design_2d', self._make_user('dr-designer', 'design_2d_member', self.design_head))
        self.designer_b = self._in('design_2d', self._make_user('dr-designer-b', 'design_2d_member', self.design_head))
        self.manager = self._in('design_2d', self._make_user('dr-manager', 'design_manager', None))
        # self.member is an Operations member (the harness).
        cur = self._cursor()
        self.client_id = fixtures.ensure_client(cur)
        cur.close()
        self.uploads = tempfile.mkdtemp()
        self.original_uploads = branding_gate.UPLOADS_DIR
        branding_gate.UPLOADS_DIR = self.uploads

    def tearDown(self):
        branding_gate.UPLOADS_DIR = self.original_uploads
        shutil.rmtree(self.uploads, ignore_errors=True)
        super().tearDown()

    def _in(self, department, user_id):
        cur = self._cursor()
        cur.execute("UPDATE user SET department_id = (SELECT id FROM department WHERE code = %s) WHERE id = %s",
                    (department, user_id))
        cur.close()
        return user_id

    def _create(self, actor=None, items=None, files=None):
        data = {'discipline': '2d', 'client_id': self.client_id, 'deadline': '2026-11-20',
                'event_date': '2026-11-25',
                'items': items or [
                    {'category': 'printing', 'title': 'Backdrop', 'size_h': '300', 'size_w': '500',
                     'size_l': '10', 'quantity': '2', 'unit': 'pcs', 'printing_type': 'Vinyl',
                     'duration': 'ignored'},
                    {'category': 'video', 'title': 'Teaser', 'size_h': '1080', 'size_w': '1920',
                     'duration': '30 s', 'quantity': '9'},
                ]}
        form = {'data': json.dumps(data)}
        form.update(files or {})
        return self._client_for(actor or self.requester).post('/api/design-requests', data=form,
                                                                content_type='multipart/form-data')

    def _post(self, actor, request_id, step, body=None):
        return self._client_for(actor).post('/api/design-requests/%d/%s' % (request_id, step), json=body or {})

    def _detail(self, actor, request_id):
        return self._client_for(actor).get('/api/design-requests/%d' % request_id)

    def test_full_flow(self):
        r = self._create(files={'files_0': (io.BytesIO(b'%PDF-1'), 'brief.pdf')})
        self.assertEqual(r.status_code, 200, r.get_json())
        rid = r.get_json()['id']

        d = self._detail(self.requester, rid).get_json()['request']
        printing, video = d['items']
        self.assertEqual((printing['size_l'], printing['quantity'], printing['printing_type'], printing['duration']),
                         (10.0, 2.0, 'Vinyl', None))
        self.assertEqual((video['size_h'], video['quantity'], video['duration']), (1080.0, None, '30 s'))
        self.assertEqual(printing['deadline'], '2026-11-20')
        self.assertEqual(len(printing['files']), 1)
        brief_url = printing['files'][0]['url']
        got = self._client_for(self.designer).get(brief_url)
        self.assertEqual((got.status_code, got.data), (200, b'%PDF-1'))
        got.close()
        self.assertEqual(self._client_for(self.other_requester).get(brief_url).status_code, 403)

        # Only Design assigns.
        self.assertEqual(self._post(self.requester, rid, 'assign', {'designer_id': self.designer}).status_code, 403)
        self.assertEqual(self._post(self.design_head, rid, 'assign', {'designer_id': self.requester}).status_code, 400)
        self.assertEqual(self._post(self.design_head, rid, 'assign', {'designer_id': self.designer}).get_json()['status'],
                         'assigned')

        # Only the assigned designer uploads, and not with nothing uploaded.
        work = lambda who: self._client_for(who).post(
            '/api/design-requests/%d/files' % rid, content_type='multipart/form-data',
            data={'files[]': (io.BytesIO(b'jpg'), 'design.jpg'), 'link': 'https://drive.example.com/x'})
        self.assertEqual(self._post(self.designer, rid, 'submit').status_code, 400)
        self.assertEqual(work(self.designer_b).status_code, 403)
        self.assertEqual(work(self.designer).get_json()['saved'], ['design.jpg', 'https://drive.example.com/x'])
        self.assertEqual(self._post(self.designer_b, rid, 'submit').status_code, 403)
        self.assertEqual(self._post(self.designer, rid, 'submit').get_json()['status'], 'in_review')

        # The Design Manager decides; a design head is not the manager.
        self.assertEqual(self._post(self.design_head, rid, 'decide', {'decision': 'approve'}).status_code, 403)
        self.assertEqual(self._post(self.manager, rid, 'decide', {'decision': 'changes'}).status_code, 400)
        self.assertEqual(self._post(self.manager, rid, 'decide', {'decision': 'changes', 'note': 'Bigger logo'})
                         .get_json()['status'], 'changes')
        self.assertEqual(self._post(self.designer, rid, 'submit').get_json()['status'], 'in_review')
        self.assertEqual(self._post(self.requester, rid, 'send').status_code, 400)
        self.assertEqual(self._post(self.manager, rid, 'decide', {'decision': 'approve'}).get_json()['status'],
                         'approved')

        # Operations sees nothing until it is sent; then it does.
        self.assertEqual(self._detail(self.member, rid).status_code, 403)
        self.assertEqual(self._post(self.other_requester, rid, 'send').status_code, 403)
        self.assertEqual(self._post(self.requester, rid, 'send').get_json()['status'], 'sent_to_operation')
        self.assertEqual(self._detail(self.member, rid).status_code, 200)
        ops = self._client_for(self.member).get('/api/design-requests').get_json()['requests']
        self.assertIn(rid, [q['id'] for q in ops])
        actions = [l['action'] for l in self._detail(self.requester, rid).get_json()['request']['log']]
        self.assertEqual(actions, ['submitted', 'assigned', 'uploaded', 'submitted_for_approval',
                                   'changes_requested', 'submitted_for_approval', 'approved', 'sent_to_operation'])

    def test_scope(self):
        rid = self._create().get_json()['id']
        ids = lambda who: [q['id'] for q in self._client_for(who).get('/api/design-requests').get_json()['requests']]
        self.assertIn(rid, ids(self.requester))
        self.assertIn(rid, ids(self.director))          # head of the requester's department
        self.assertIn(rid, ids(self.design_head))
        self.assertNotIn(rid, ids(self.other_requester))
        self.assertNotIn(rid, ids(self.member))         # Operations: not sent yet
        self.assertEqual(self._detail(self.other_requester, rid).status_code, 403)
        can = self._detail(self.director, rid).get_json()['can']
        self.assertTrue(can['cancel'])
        self.assertFalse(can['assign'])

    def test_cancel_only_before_work_is_submitted(self):
        rid = self._create().get_json()['id']
        self.assertEqual(self._post(self.designer, rid, 'cancel').status_code, 403)
        self.assertEqual(self._post(self.requester, rid, 'cancel').get_json()['status'], 'cancelled')
        self.assertEqual(self._post(self.design_head, rid, 'assign', {'designer_id': self.designer}).status_code, 400)

    def test_refuses_bad_input(self):
        self.assertEqual(self._create(items=[{'category': 'printing', 'title': ''}]).status_code, 400)
        self.assertEqual(self._create(items=[{'category': 'nope', 'title': 'x'}]).status_code, 400)
        self.assertEqual(self._create(items=[{'category': 'printing', 'title': 'x',
                                              'printing_type': 'Gold'}]).status_code, 400)
        self.assertEqual(self._create(actor=self.designer).status_code, 403)

    def test_workflow_rules(self):
        self.assertEqual(design_workflow.transition('changes', 'assign'), 'changes')
        with self.assertRaises(design_workflow.WorkflowError):
            design_workflow.transition('approved', 'cancel')
        item = design_workflow.clean_item({'category': 'social_media', 'title': 'Post', 'size_h': '5'})
        self.assertIsNone(item['size_h'])


if __name__ == '__main__':
    unittest.main()
