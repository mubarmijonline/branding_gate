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

    def _create(self, actor=None, items=None, files=None, extra=None):
        data = {'discipline': '2d', 'client_id': self.client_id, 'deadline': '2026-11-20',
                'event_date': '2026-11-25',
                'items': items or [
                    {'category': 'printing', 'title': 'Backdrop', 'size_h': '300', 'size_w': '500',
                     'size_l': '10', 'quantity': '2', 'unit': 'pcs', 'printing_type': 'Vinyl',
                     'duration': 'ignored'},
                    {'category': 'video', 'title': 'Teaser', 'size_h': '1080', 'size_w': '1920',
                     'duration': '30 s', 'quantity': '9'},
                ]}
        data.update(extra or {})
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

        d = self._detail(self.designer, rid).get_json()['request']
        backdrop, teaser = [i['id'] for i in d['items']]

        # Only the assigned designer uploads, to one item, and submits only with work.
        def work(who, item, name='design.jpg', link=None):
            data = {'item_id': str(item), 'files[]': (io.BytesIO(b'jpg-' + name.encode()), name)}
            if link:
                data['link'] = link
            return self._client_for(who).post('/api/design-requests/%d/files' % rid,
                                              content_type='multipart/form-data', data=data)
        item = lambda who, i, step, body=None: self._post(who, rid, 'items/%d/%s' % (i, step), body)
        self.assertEqual(item(self.designer, backdrop, 'submit').status_code, 400)
        self.assertEqual(work(self.designer_b, backdrop).status_code, 403)
        self.assertEqual(work(self.designer, backdrop, 'v1.jpg', 'https://drive.example.com/x').get_json()['saved'],
                         ['v1.jpg', 'https://drive.example.com/x'])
        self.assertEqual(item(self.designer_b, backdrop, 'submit').status_code, 403)
        r = item(self.designer, backdrop, 'submit').get_json()
        self.assertEqual((r['item_status'], r['status']), ('in_review', 'in_review'))
        # The other item is still being worked on; it does not hold this one up.
        self.assertEqual(work(self.designer, teaser, 'teaser.jpg').status_code, 200)

        # The Design Manager decides per item; a design head is not the manager.
        self.assertEqual(item(self.design_head, backdrop, 'decide', {'decision': 'approve'}).status_code, 403)
        self.assertEqual(item(self.manager, backdrop, 'decide', {'decision': 'changes'}).status_code, 400)
        self.assertEqual(item(self.manager, backdrop, 'decide', {'decision': 'changes', 'note': 'Bigger logo'})
                         .get_json()['item_status'], 'changes')
        # A returned item needs new work before it goes back.
        self.assertEqual(item(self.designer, backdrop, 'submit').status_code, 400)
        self.assertEqual(work(self.designer, backdrop, 'v2.jpg').status_code, 200)
        self.assertEqual(item(self.designer, backdrop, 'submit').get_json()['item_status'], 'in_review')
        self.assertEqual(self._post(self.requester, rid, 'send').status_code, 400)
        r = item(self.manager, backdrop, 'decide', {'decision': 'approve'}).get_json()
        self.assertEqual((r['item_status'], r['status']), ('approved', 'assigned'))

        # Operations sees nothing until something is sent; then only that item's final round.
        self.assertEqual(self._detail(self.member, rid).status_code, 403)
        self.assertEqual(self._post(self.other_requester, rid, 'send').status_code, 403)
        self.assertEqual(self._post(self.requester, rid, 'send').get_json()['sent'], 1)
        ops = self._detail(self.member, rid).get_json()['request']
        self.assertEqual([i['title'] for i in ops['items']], ['Backdrop'])
        self.assertEqual([f['name'] for f in ops['items'][0]['final']], ['v2.jpg'])
        self.assertEqual((ops['items'][0]['history'], ops['items'][0]['drafts'], ops['log']), ([], [], []))
        self.assertIn(rid, [q['id'] for q in self._client_for(self.member).get('/api/design-requests').get_json()['requests']])

        # The requester still sees every round.
        full = self._detail(self.requester, rid).get_json()['request']['items'][0]
        self.assertEqual([[f['name'] for f in h['files']] for h in full['history']],
                         [['v1.jpg', 'https://drive.example.com/x']])
        urls = {f['name']: f['url'] for f in full['history'][0]['files'] + full['final']}
        get = lambda who, url: self._client_for(who).get(url)
        self.assertEqual(get(self.member, urls['v2.jpg']).status_code, 200)
        self.assertEqual(get(self.member, urls['v1.jpg']).status_code, 403)
        self.assertEqual(get(self.requester, urls['v1.jpg']).status_code, 200)

        # Handed-in work stays; only drafts can be taken back.
        old = full['history'][0]['files'][0]['id']
        self.assertEqual(self._client_for(self.designer).delete('/api/design-requests/%d/files/%d' % (rid, old)).status_code, 404)

        # The teaser finishes later and goes the same way; the request is done when both are sent.
        item(self.designer, teaser, 'submit')
        item(self.manager, teaser, 'decide', {'decision': 'approve'})
        self.assertEqual(self._post(self.requester, rid, 'send').get_json()['status'], 'sent_to_operation')
        actions = [l['action'] for l in self._detail(self.requester, rid).get_json()['request']['log']]
        self.assertEqual(actions, ['submitted', 'assigned', 'uploaded', 'submitted_for_approval', 'uploaded',
                                   'changes_requested', 'uploaded', 'submitted_for_approval', 'approved',
                                   'sent_to_operation', 'submitted_for_approval', 'approved', 'sent_to_operation'])

    def test_several_brief_files_and_a_job_code(self):
        cur = self._cursor()
        cur.execute("UPDATE sales_request SET owner_user_id = %s WHERE id = %s", (self.requester, self.request_id))
        cur.close()
        r = self._create(files={'files_0': [(io.BytesIO(b'a'), 'a.pdf'), (io.BytesIO(b'b'), 'b.png')]},
                         extra={'sales_request_id': self.request_id})
        self.assertEqual(r.status_code, 200, r.get_json())
        d = self._detail(self.requester, r.get_json()['id']).get_json()['request']
        self.assertEqual([f['name'] for f in d['items'][0]['files']], ['a.pdf', 'b.png'])
        self.assertEqual(d['sales_request']['id'], self.request_id)
        # A sales request the requester cannot see is refused.
        self.assertEqual(self._create(actor=self.other_requester, extra={'sales_request_id': self.request_id}).status_code, 400)

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
        self._post(self.design_head, rid, 'assign', {'designer_id': self.designer})
        first = self._detail(self.designer, rid).get_json()['request']['items'][0]['id']
        self._client_for(self.designer).post('/api/design-requests/%d/files' % rid, content_type='multipart/form-data',
                                             data={'item_id': str(first), 'files[]': (io.BytesIO(b'x'), 'x.jpg')})
        self._post(self.designer, rid, 'items/%d/submit' % first)
        self.assertEqual(self._post(self.requester, rid, 'cancel').status_code, 400)
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
        with self.assertRaises(design_workflow.WorkflowError):
            design_workflow.item_transition('open', 'approve')
        self.assertEqual(design_workflow.request_status('assigned', True, ['sent', 'in_review']), 'in_review')
        item = design_workflow.clean_item({'category': 'social_media', 'title': 'Post', 'size_h': '5'})
        self.assertIsNone(item['size_h'])


if __name__ == '__main__':
    unittest.main()
