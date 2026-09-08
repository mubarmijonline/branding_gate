"""
Costing by assignment: the rules alone, and the whole chain end to end.

The DB half uses the harness from test_scope.py -- a real connection with
autocommit off, branding_gate.connection monkeypatched, rollback in tearDown.
Nothing survives.
"""

import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate
import fixtures
import costing
import rbac


class CostingRulesTest(unittest.TestCase):
    """The refusals, with no database in sight."""

    def test_self_check_passes(self):
        costing.demo()

    def test_you_may_only_assign_to_your_own_reports(self):
        self.assertTrue(costing.check_assignment(1, 2, [2, 3]))
        with self.assertRaises(costing.CostingError):
            costing.check_assignment(1, 9, [2, 3])

    def test_you_may_not_assign_to_yourself(self):
        with self.assertRaises(costing.CostingError):
            costing.check_assignment(1, 1, [1, 2])

    def test_the_head_reaches_past_their_own_reports(self):
        self.assertTrue(costing.check_assignment(1, 9, [], unrestricted=True))

    def test_a_withdrawn_assignment_takes_no_proposals(self):
        with self.assertRaises(costing.CostingError):
            costing.check_proposal(costing.ASSIGNMENT_WITHDRAWN)

    def test_a_decided_proposal_is_a_record_not_a_draft(self):
        with self.assertRaises(costing.CostingError):
            costing.check_proposal(costing.ASSIGNMENT_OPEN, costing.PROPOSAL_ACCEPTED)

    def test_only_the_asker_decides(self):
        self.assertTrue(costing.check_decision(costing.PROPOSAL_SUBMITTED, 5, 5))
        with self.assertRaises(costing.CostingError):
            costing.check_decision(costing.PROPOSAL_SUBMITTED, 7, 5)

    def test_an_accepted_proposal_is_visible_to_everyone(self):
        rows = [{'id': 1, 'author_id': 10, 'assigned_by': 5,
                 'status': costing.PROPOSAL_ACCEPTED}]
        self.assertEqual(costing.visible_proposal_ids(rows, 999, []), rows)

    def test_a_stranger_sees_no_undecided_proposal(self):
        rows = [{'id': 1, 'author_id': 10, 'assigned_by': 5,
                 'status': costing.PROPOSAL_SUBMITTED}]
        self.assertEqual(costing.visible_proposal_ids(rows, 999, []), [])

    def test_a_negative_cost_is_refused(self):
        with self.assertRaises(ValueError):
            costing.parse_amount('-1')


class CostingPolicyTest(unittest.TestCase):
    """The grant matrix says what the workflow needs."""

    def test_only_the_head_and_leaders_type_a_cost_directly(self):
        # A leader may cost an item themselves when it needs no proposals.
        # A member never can: their number arrives as a proposal and is accepted.
        for role in ('operations_manager', 'operations_team_leader'):
            self.assertIn('sales_item.cost_direct', rbac.SEED_MATRIX[role], role)
        self.assertNotIn('sales_item.cost_direct', rbac.SEED_MATRIX['operations_member'])

    def test_each_role_sees_only_its_own_section(self):
        sections = lambda code: sorted(
            k for k in rbac.SEED_MATRIX[code] if k.startswith('section.'))
        # Operations reads sales requests to cost them, but the Sales menu is
        # not theirs -- that is what gating on sales_request.view got wrong.
        for role in ('operations_manager', 'operations_team_leader', 'operations_member'):
            self.assertEqual(sections(role), ['section.operations'], role)
            self.assertIn('sales_request.view', rbac.SEED_MATRIX[role], role)
        for role in ('sales_head', 'sales_member', 'account_director', 'account_member'):
            self.assertEqual(sections(role), ['section.sales'], role)
        self.assertEqual(sections('finance_manager'), ['section.finance'])
        # Pricing works inside the Operations menu.
        self.assertEqual(sections('pricing_manager'), ['section.operations'])

    def test_operations_below_the_manager_cannot_edit_a_sales_request(self):
        for role in ('operations_team_leader', 'operations_member'):
            self.assertNotIn('sales_request.edit', rbac.SEED_MATRIX[role], role)
            self.assertNotIn('sales_request.create', rbac.SEED_MATRIX[role], role)

    def test_seeing_cost_is_not_setting_it(self):
        # Everyone in Operations still sees cost columns; that is a different
        # permission from typing one in.
        for role in ('operations_manager', 'operations_team_leader', 'operations_member'):
            self.assertIn('sales_item.cost', rbac.SEED_MATRIX[role], role)

    def test_the_ladder_can_assign_decide_and_propose(self):
        head = rbac.SEED_MATRIX['operations_manager']
        leader = rbac.SEED_MATRIX['operations_team_leader']
        member = rbac.SEED_MATRIX['operations_member']
        self.assertEqual(head['costing.assign'], 'all')
        self.assertEqual(head['costing.decide'], 'all')
        self.assertEqual(leader['costing.assign'], 'team')
        self.assertEqual(leader['costing.propose'], 'own')
        self.assertEqual(member['costing.propose'], 'own')
        self.assertNotIn('costing.assign', member)
        self.assertNotIn('costing.decide', member)

    def test_sales_holds_none_of_it(self):
        for role in ('sales_head', 'sales_member'):
            for code in ('costing.assign', 'costing.propose', 'costing.decide'):
                self.assertNotIn(code, rbac.SEED_MATRIX[role], '%s / %s' % (role, code))


class _RollbackConnection:
    def __init__(self, raw_connection):
        self.raw_connection = raw_connection

    def commit(self):
        pass

    def close(self):
        pass

    def rollback(self):
        self.raw_connection.rollback()


class _CostingHarness(unittest.TestCase):
    """
    A department, a request and an item, on a connection that is rolled back.

    Fixtures only, no tests: every class below reuses these, and when they were
    part of the chain test each one re-ran the whole chain along with them.
    """

    def setUp(self):
        self.raw_connection = MySQLdb.connect(
            host="localhost", user="ps", passwd="Aa@123456", db="branding_gate",
            port=3306, charset="utf8mb4", use_unicode=True,
        )
        self.raw_connection.autocommit(False)
        self.wrapper = _RollbackConnection(self.raw_connection)
        self.original_connection = branding_gate.connection
        branding_gate.connection = self._connection

        cur = self._cursor()
        cur.execute("SELECT id FROM department WHERE code = 'operations'")
        self.department_id = cur.fetchone()["id"]
        self.roles = {}
        for code in ("operations_manager", "operations_team_leader",
                     "operations_member", "sales_member"):
            cur.execute("SELECT id FROM rbac_role WHERE code = %s", (code,))
            self.roles[code] = cur.fetchone()["id"]
        client_id = fixtures.ensure_client(cur)

        self.head = self._make_user("cost-head", "operations_manager", None)
        self.leader = self._make_user("cost-leader", "operations_team_leader", self.head)
        self.leader_b = self._make_user("cost-leader-b", "operations_team_leader", self.head)
        self.member = self._make_user("cost-member", "operations_member", self.leader)
        self.member_b = self._make_user("cost-member-b", "operations_member", self.leader)
        self.outsider = self._make_user("cost-outsider", "operations_member", self.leader_b)

        cur.execute("""
            INSERT INTO sales_request (client_id, title, start_date, created_by,
                                       items_count, owner_user_id)
            VALUES (%s, 'Costing test request', CURDATE(), 'costing-test', 1, %s)
        """, (client_id, self.head))
        self.request_id = cur.lastrowid
        cur.execute("""
            INSERT INTO sales_request_items (request_id, name, qty)
            VALUES (%s, 'Costing test item', 4)
        """, (self.request_id,))
        self.item_id = cur.lastrowid
        cur.close()

    def tearDown(self):
        branding_gate.connection = self.original_connection
        self.raw_connection.rollback()
        self.raw_connection.close()

    def _cursor(self):
        return self.raw_connection.cursor(MySQLdb.cursors.DictCursor)

    def _connection(self):
        return self.wrapper, self._cursor()

    def _make_user(self, username, role_code, manager_id):
        cur = self._cursor()
        cur.execute(
            """
            INSERT INTO user (name, mobile, email, password, username, title,
                              department_id, rbac_role_id, manager_id, date)
            VALUES (%s, %s, %s, 'x', %s, 'Costing Test', %s, %s, %s, NOW())
            """,
            (username, '017%08d' % (abs(hash(username)) % 10**8),
             username + '@example.com', username, self.department_id,
             self.roles[role_code], manager_id),
        )
        user_id = cur.lastrowid
        cur.close()
        return user_id

    def _client_for(self, user_id):
        perms, role_code = branding_gate.load_permissions(user_id)
        client = branding_gate.app.test_client()
        with client.session_transaction() as flask_session:
            flask_session.update({
                "user_id": user_id, "mobile": "m", "email": "e",
                "username": "u", "name": "n",
                "roles": [role_code], "perms": perms, "role_code": role_code,
            })
        return client

    def _assign(self, actor, assignees, note=''):
        return self._client_for(actor).post('/api/costing/assign', json={
            'item_id': self.item_id, 'assignee_ids': assignees, 'note': note})

    def _assignment_id(self, assignee):
        cur = self._cursor()
        cur.execute("""
            SELECT id FROM costing_assignment WHERE item_id = %s AND assignee_id = %s
        """, (self.item_id, assignee))
        row = cur.fetchone()
        cur.close()
        return row['id'] if row else None

    def _propose(self, actor, amount, notes=''):
        return self._client_for(actor).post('/api/costing/proposals', json={
            'assignment_id': self._assignment_id(actor),
            'amount': amount, 'notes': notes})

    def _item_cost(self):
        cur = self._cursor()
        cur.execute("SELECT cost_per_item, total_cost FROM sales_request_items WHERE id = %s",
                    (self.item_id,))
        row = cur.fetchone()
        cur.close()
        return row

    def _log_actions(self):
        cur = self._cursor()
        cur.execute("SELECT action FROM costing_log WHERE item_id = %s ORDER BY id",
                    (self.item_id,))
        actions = [r['action'] for r in cur.fetchall()]
        cur.close()
        return actions


class CostingChainTest(_CostingHarness):
    """Head -> leaders -> members -> proposals -> one accepted, over the routes."""

    def test_the_head_assigns_several_leaders_at_once(self):
        response = self._assign(self.head, [self.leader, self.leader_b])
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(sorted(response.get_json()['assigned']),
                         sorted([self.leader, self.leader_b]))

    def test_a_leader_assigns_several_of_their_own_people(self):
        self._assign(self.head, [self.leader])
        response = self._assign(self.leader, [self.member, self.member_b])
        self.assertEqual(response.status_code, 200, response.get_json())

    def test_a_leader_cannot_assign_outside_their_team(self):
        self._assign(self.head, [self.leader])
        response = self._assign(self.leader, [self.outsider])
        self.assertEqual(response.status_code, 403)
        self.assertIn('your own team', response.get_json()['error'])

    def test_a_member_cannot_assign_at_all(self):
        response = self._assign(self.member, [self.member_b])
        self.assertEqual(response.status_code, 403)

    def test_one_person_may_put_up_several_proposals(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        self.assertEqual(self._propose(self.member, '1000').status_code, 200)
        self.assertEqual(self._propose(self.member, '1,250.50').status_code, 200)
        cur = self._cursor()
        cur.execute("SELECT COUNT(*) AS n FROM costing_proposal WHERE author_id = %s",
                    (self.member,))
        self.assertEqual(cur.fetchone()['n'], 2)
        cur.close()

    def test_a_proposal_needs_an_assignment(self):
        response = self._client_for(self.member).post('/api/costing/proposals', json={
            'assignment_id': 999999, 'amount': '100'})
        self.assertEqual(response.status_code, 404)

    def test_you_cannot_propose_on_somebody_elses_assignment(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        response = self._client_for(self.member_b).post('/api/costing/proposals', json={
            'assignment_id': self._assignment_id(self.member), 'amount': '100'})
        self.assertEqual(response.status_code, 403)

    def test_accepting_writes_the_item_cost_and_rejects_the_rest(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member, self.member_b])
        first = self._propose(self.member, '1000').get_json()['proposal_id']
        self._propose(self.member_b, '900')

        response = self._client_for(self.leader).post(
            '/api/costing/proposals/%d/decide' % first,
            json={'decision': 'accept', 'note': 'best quote'})
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertEqual(payload['amount'], 1000.0)
        self.assertEqual(payload['rejected'], 1)

        cost = self._item_cost()
        self.assertEqual(float(cost['cost_per_item']), 1000.0)
        # qty is 4 on the test item, so the total follows the amount.
        self.assertEqual(float(cost['total_cost']), 4000.0)

    def test_a_leader_cannot_decide_a_proposal_they_did_not_ask_for(self):
        self._assign(self.head, [self.leader, self.leader_b])
        self._assign(self.leader, [self.member])
        proposal = self._propose(self.member, '1000').get_json()['proposal_id']
        response = self._client_for(self.leader_b).post(
            '/api/costing/proposals/%d/decide' % proposal, json={'decision': 'accept'})
        self.assertEqual(response.status_code, 403)

    def test_the_head_can_decide_anywhere(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        proposal = self._propose(self.member, '750').get_json()['proposal_id']
        response = self._client_for(self.head).post(
            '/api/costing/proposals/%d/decide' % proposal, json={'decision': 'accept'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(float(self._item_cost()['cost_per_item']), 750.0)

    def test_a_decided_proposal_cannot_be_decided_twice(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        proposal = self._propose(self.member, '500').get_json()['proposal_id']
        self._client_for(self.leader).post(
            '/api/costing/proposals/%d/decide' % proposal, json={'decision': 'accept'})
        again = self._client_for(self.leader).post(
            '/api/costing/proposals/%d/decide' % proposal, json={'decision': 'reject'})
        self.assertEqual(again.status_code, 403)

    def test_rejecting_leaves_the_cost_alone(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        proposal = self._propose(self.member, '500').get_json()['proposal_id']
        response = self._client_for(self.leader).post(
            '/api/costing/proposals/%d/decide' % proposal,
            json={'decision': 'reject', 'note': 'too high'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self._item_cost()['cost_per_item'])

    def test_withdrawing_an_assignment_stops_further_proposals(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        assignment = self._assignment_id(self.member)
        response = self._client_for(self.leader).post(
            '/api/costing/assignments/%d/withdraw' % assignment)
        self.assertEqual(response.status_code, 200)
        blocked = self._propose(self.member, '100')
        self.assertEqual(blocked.status_code, 403)

    # -- the trail ----------------------------------------------------------

    def test_every_step_is_logged(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member, self.member_b])
        first = self._propose(self.member, '1000').get_json()['proposal_id']
        self._propose(self.member_b, '900')
        self._client_for(self.leader).post(
            '/api/costing/proposals/%d/decide' % first, json={'decision': 'accept'})

        actions = self._log_actions()
        self.assertEqual(actions.count('assigned'), 3)
        self.assertEqual(actions.count('proposal_submitted'), 2)
        self.assertEqual(actions.count('proposal_accepted'), 1)
        self.assertEqual(actions.count('proposal_rejected'), 1)

    def test_the_log_route_returns_the_trail(self):
        self._assign(self.head, [self.leader])
        response = self._client_for(self.head).get(
            '/api/costing/items/%d/log' % self.item_id)
        self.assertEqual(response.status_code, 200)
        entries = response.get_json()['entries']
        self.assertTrue(entries)
        self.assertEqual(entries[0]['action'], 'assigned')

    # -- being told there is something waiting -------------------------------

    def _summary(self, actor):
        response = self._client_for(actor).get('/api/costing/summary')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload.get('success'), payload)
        return payload

    def test_an_assignee_is_told_the_item_is_on_their_desk(self):
        before = self._summary(self.member)['mine_total']
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        after = self._summary(self.member)
        self.assertEqual(after['mine_total'], before + 1)
        self.assertEqual(after['by_request'][str(self.request_id)]['mine'], 1)

    def test_the_asking_leader_is_told_a_proposal_is_waiting(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        self.assertEqual(
            self._summary(self.leader)['by_request'][str(self.request_id)]
            ['awaiting_decision'], 0)
        self._propose(self.member, '1000')
        summary = self._summary(self.leader)
        self.assertEqual(
            summary['by_request'][str(self.request_id)]['awaiting_decision'], 1)
        # And it is not somebody else's problem to chase.
        self.assertEqual(
            self._summary(self.leader_b)['by_request']
            .get(str(self.request_id), {}).get('awaiting_decision', 0), 0)

    def test_the_count_clears_once_a_proposal_is_accepted(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        proposal = self._propose(self.member, '1000').get_json()['proposal_id']
        self._client_for(self.leader).post(
            '/api/costing/proposals/%d/decide' % proposal, json={'decision': 'accept'})
        leader = self._summary(self.leader)['by_request'].get(str(self.request_id), {})
        member = self._summary(self.member)['by_request'].get(str(self.request_id), {})
        self.assertEqual(leader.get('awaiting_decision', 0), 0)
        self.assertEqual(member.get('mine', 0), 0)

    # -- who sees what ------------------------------------------------------

    def test_a_member_does_not_see_a_peers_proposal(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member, self.member_b])
        self._propose(self.member, '1000')
        self._propose(self.member_b, '900')

        payload = self._client_for(self.member).get('/api/costing/queue').get_json()
        amounts = [p['amount'] for card in payload['mine'] for p in card['proposals']]
        self.assertIn(1000.0, amounts)
        self.assertNotIn(900.0, amounts)

    def test_the_asking_leader_sees_every_proposal(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member, self.member_b])
        self._propose(self.member, '1000')
        self._propose(self.member_b, '900')

        payload = self._client_for(self.leader).get('/api/costing/queue').get_json()
        amounts = sorted({p['amount'] for card in payload['given'] for p in card['proposals']})
        self.assertEqual(amounts, [900.0, 1000.0])

    def test_a_leader_may_only_offer_their_own_team_to_assign_to(self):
        payload = self._client_for(self.leader).get('/api/costing/team').get_json()
        ids = {p['id'] for p in payload['people']}
        self.assertIn(self.member, ids)
        self.assertIn(self.member_b, ids)
        self.assertNotIn(self.outsider, ids)

    def test_both_ways_a_cost_can_arrive_agree(self):
        # A rental item multiplies by days as well as quantity. The accepted
        # proposal must land the same total the direct route would.
        cur = self._cursor()
        cur.execute("""
            UPDATE sales_request_items
            SET sell_type = 'rent', rental_days = 3, include_days_in_calc = 1
            WHERE id = %s
        """, (self.item_id,))
        cur.close()

        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        proposal = self._propose(self.member, '100').get_json()['proposal_id']
        self._client_for(self.leader).post(
            '/api/costing/proposals/%d/decide' % proposal, json={'decision': 'accept'})
        accepted = float(self._item_cost()['total_cost'])

        self._client_for(self.head).post('/api/operations/requests/add-costs', json={
            'request_id': self.request_id,
            'items': [{'id': self.item_id, 'cost_per_item': 100}]})
        typed = float(self._item_cost()['total_cost'])

        self.assertEqual(accepted, typed)
        # qty 4 x 3 days x 100
        self.assertEqual(accepted, 1200.0)

    # -- re-costing, which arrives through the same desk ---------------------

    def _open_recosting(self):
        """Pricing sends the item back for a new cost."""
        cur = self._cursor()
        cur.execute("""
            INSERT INTO negotiation_requests
                (item_id, request_id, client_expected_price, client_reason,
                 status, destination_team)
            VALUES (%s, %s, 80.00, 'Client wants a better price',
                    'pending_costing', 'costing')
        """, (self.item_id, self.request_id))
        negotiation_id = cur.lastrowid
        cur.execute("""
            UPDATE sales_request_items
            SET cost_per_item = 100, approval_status = 'pending_negotiation',
                negotiation_status = 'pending_negotiation'
            WHERE id = %s
        """, (self.item_id,))
        cur.close()
        return negotiation_id

    def _negotiation(self, negotiation_id):
        cur = self._cursor()
        cur.execute("SELECT status, new_cost_price, destination_team "
                    "FROM negotiation_requests WHERE id = %s", (negotiation_id,))
        row = cur.fetchone()
        cur.close()
        return row

    def test_accepting_a_proposal_finishes_a_re_costing(self):
        # Before this, only a cost typed in by the Head moved the negotiation
        # on; one costed through the desk sat in pending_costing for ever.
        negotiation_id = self._open_recosting()
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        proposal = self._propose(self.member, '60').get_json()['proposal_id']

        response = self._client_for(self.leader).post(
            '/api/costing/proposals/%d/decide' % proposal, json={'decision': 'accept'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['recosted_negotiation'], negotiation_id)

        after = self._negotiation(negotiation_id)
        self.assertEqual(after['status'], 'pending_pricing')
        self.assertEqual(float(after['new_cost_price']), 60.0)
        self.assertEqual(after['destination_team'], 'pricing')
        self.assertEqual(float(self._item_cost()['cost_per_item']), 60.0)

    def test_the_two_ways_of_re_costing_agree(self):
        # Typed by the Head, or accepted on the desk: the negotiation ends in
        # the same state either way.
        typed_negotiation = self._open_recosting()
        self._client_for(self.head).post('/api/operations/requests/add-costs', json={
            'request_id': self.request_id,
            'items': [{'id': self.item_id, 'cost_per_item': 60}]})
        typed = self._negotiation(typed_negotiation)
        self.assertEqual(typed['status'], 'pending_pricing')
        self.assertEqual(float(typed['new_cost_price']), 60.0)

    def test_a_plain_costing_touches_no_negotiation(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        proposal = self._propose(self.member, '5').get_json()['proposal_id']
        response = self._client_for(self.leader).post(
            '/api/costing/proposals/%d/decide' % proposal, json={'decision': 'accept'})
        self.assertIsNone(response.get_json()['recosted_negotiation'])

    def test_the_summary_counts_what_was_sent_back(self):
        before = self._client_for(self.head).get('/api/costing/summary').get_json()
        self._open_recosting()
        after = self._client_for(self.head).get('/api/costing/summary').get_json()
        # An absolute total would depend on whatever else is mid-negotiation in
        # this database, so measure the change this test caused.
        self.assertEqual(after['recost_total'], before['recost_total'] + 1)
        self.assertEqual(after['by_request'][str(self.request_id)]['recost'], 1)

    def test_direct_costing_is_closed_to_members_only(self):
        payload = {'request_id': self.request_id,
                   'items': [{'id': self.item_id, 'cost_per_item': 5}]}
        # A member's number arrives as a proposal, never typed straight in.
        self.assertEqual(
            self._client_for(self.member).post(
                '/api/operations/requests/add-costs', json=payload).status_code,
            403)
        # The Head and the team leaders may cost an item that needs no proposals.
        for actor in (self.head, self.leader):
            self.assertEqual(
                self._client_for(actor).post(
                    '/api/operations/requests/add-costs', json=payload).status_code,
                200, actor)


class WholeRequestAssignmentTest(_CostingHarness):
    """
    The Head hands over a request; the leader splits it.

    The client's rule: David does not pick items. He picks a request and a
    leader, and the leader does the per-item split with their own people.
    """

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        self.other_items = []
        for name in ('Second item', 'Third item'):
            cur.execute("""
                INSERT INTO sales_request_items (request_id, name, qty)
                VALUES (%s, %s, 2)
            """, (self.request_id, name))
            self.other_items.append(cur.lastrowid)
        cur.execute("UPDATE sales_request SET items_count = 3 WHERE id = %s",
                    (self.request_id,))
        cur.close()

    def _assign_request(self, actor, assignees, **extra):
        payload = {'request_id': self.request_id, 'assignee_ids': assignees}
        payload.update(extra)
        return self._client_for(actor).post('/api/costing/assign-request', json=payload)

    def _assigned_items(self, assignee):
        cur = self._cursor()
        cur.execute("""
            SELECT item_id FROM costing_assignment
            WHERE request_id = %s AND assignee_id = %s AND status = 'open'
            ORDER BY item_id
        """, (self.request_id, assignee))
        items = [r['item_id'] for r in cur.fetchall()]
        cur.close()
        return items

    def test_the_whole_request_lands_on_the_leader(self):
        response = self._assign_request(self.head, [self.leader])
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['items'], 3)
        self.assertEqual(self._assigned_items(self.leader),
                         sorted([self.item_id] + self.other_items))

    def test_the_leader_then_splits_it_item_by_item(self):
        self._assign_request(self.head, [self.leader])
        # The per-item route is unchanged: this is the same call a leader made
        # before, one level down.
        response = self._assign(self.leader, [self.member])
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self._assigned_items(self.member), [self.item_id])

    def test_an_item_that_is_already_costed_is_left_alone(self):
        cur = self._cursor()
        cur.execute("UPDATE sales_request_items SET cost_per_item = 25 WHERE id = %s",
                    (self.item_id,))
        cur.close()
        response = self._assign_request(self.head, [self.leader])
        body = response.get_json()
        self.assertEqual(body['items'], 2)
        self.assertEqual(body['skipped_costed'], 1)
        self.assertNotIn(self.item_id, self._assigned_items(self.leader))

    def test_a_costed_item_can_be_asked_for_again_on_purpose(self):
        cur = self._cursor()
        cur.execute("UPDATE sales_request_items SET cost_per_item = 25 WHERE id = %s",
                    (self.item_id,))
        cur.close()
        response = self._assign_request(self.head, [self.leader], include_costed=True)
        self.assertEqual(response.get_json()['items'], 3)
        self.assertIn(self.item_id, self._assigned_items(self.leader))

    def test_a_leader_still_cannot_reach_outside_their_team(self):
        response = self._assign_request(self.leader, [self.outsider])
        self.assertEqual(response.status_code, 403)
        self.assertIn('your own team', response.get_json()['error'])

    def test_several_items_go_out_in_one_call(self):
        # The modal picks items with checkboxes and assigns them together;
        # eleven items should not be eleven dialogs and eleven round trips.
        response = self._client_for(self.head).post('/api/costing/assign', json={
            'item_ids': [self.item_id] + self.other_items,
            'assignee_ids': [self.leader]})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['items'], 3)
        self.assertEqual(self._assigned_items(self.leader),
                         sorted([self.item_id] + self.other_items))

    def test_one_item_still_goes_out_on_its_own(self):
        # The old shape stays: a card assigns just itself.
        response = self._client_for(self.head).post('/api/costing/assign', json={
            'item_id': self.item_id, 'assignee_ids': [self.leader]})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self._assigned_items(self.leader), [self.item_id])

    def test_a_bad_item_in_the_list_assigns_none_of_them(self):
        response = self._client_for(self.head).post('/api/costing/assign', json={
            'item_ids': [self.item_id, 99999999], 'assignee_ids': [self.leader]})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self._assigned_items(self.leader), [])

    def test_only_team_leaders_are_offered_a_whole_request(self):
        # The Head hands a request to a leader; the split among members is the
        # leader's job, so members are not in that list.
        everyone = self._client_for(self.head).get('/api/costing/team').get_json()['people']
        leaders = self._client_for(self.head).get(
            '/api/costing/team?leaders=1').get_json()['people']
        names = {p['id'] for p in everyone}
        leader_ids = {p['id'] for p in leaders}
        self.assertIn(self.member, names)
        self.assertNotIn(self.member, leader_ids)
        self.assertIn(self.leader, leader_ids)
        self.assertTrue(all(p['level'] == rbac.LEVEL_TEAM_LEADER for p in leaders))

    def test_a_member_cannot_hand_out_a_request(self):
        self.assertEqual(
            self._assign_request(self.member, [self.member_b]).status_code, 403)

    def test_every_item_is_on_the_trail(self):
        self._assign_request(self.head, [self.leader])
        cur = self._cursor()
        cur.execute("""
            SELECT COUNT(*) AS n FROM costing_log
            WHERE request_id = %s AND action = 'assigned'
        """, (self.request_id,))
        self.assertEqual(cur.fetchone()['n'], 3)
        cur.close()


class OperationsListScopeTest(_CostingHarness):
    """
    Everyone sees their own work on /operation_request, and nobody else's.

    Before this the list was every request in the company, for everybody.
    """

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        cur.execute("""
            INSERT INTO sales_request_items (request_id, name, qty)
            VALUES (%s, 'Not their item', 2)
        """, (self.request_id,))
        self.other_item = cur.lastrowid
        cur.execute("UPDATE sales_request SET items_count = 2 WHERE id = %s",
                    (self.request_id,))
        cur.close()

    def _rows(self, actor):
        response = self._client_for(actor).get('/api/operations/requests')
        self.assertEqual(response.status_code, 200)
        return {r['request_id']: r for r in response.get_json()['requests']}

    def test_the_head_still_sees_the_whole_board(self):
        rows = self._rows(self.head)
        self.assertIn(self.request_id, rows)
        self.assertFalse(rows[self.request_id]['scoped_to_me'])

    def test_a_member_sees_nothing_until_something_is_assigned(self):
        self.assertNotIn(self.request_id, self._rows(self.member))

    def test_a_member_sees_the_request_holding_their_item(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        rows = self._rows(self.member)
        self.assertIn(self.request_id, rows)
        # One of the two items is theirs, and that is what the row counts.
        self.assertEqual(rows[self.request_id]['items_count'], 1)
        self.assertEqual(rows[self.request_id]['request_items_count'], 2)
        self.assertTrue(rows[self.request_id]['scoped_to_me'])

    def test_a_leader_sees_what_they_handed_down(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        self.assertIn(self.request_id, self._rows(self.leader))

    def test_another_team_sees_none_of_it(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        self.assertNotIn(self.request_id, self._rows(self.outsider))

    def test_withdrawing_takes_it_off_their_page(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        assignment_id = self._assignment_id(self.member)
        self._client_for(self.leader).post(
            '/api/costing/assignments/%d/withdraw' % assignment_id)
        self.assertNotIn(self.request_id, self._rows(self.member))


class EmptyRequestTest(_CostingHarness):
    """
    A request raised with no items at all.

    Sales can submit a request with the template's own fields filled in and
    nothing to build -- request #786 on the live system is one. The operations
    list used to count one item pending on it, because a LEFT JOIN gives a
    request with no items a single row of NULLs and `cost_per_item IS NULL` is
    true of that row. So an empty request offered an "Add Costs" button that
    opened a modal with nothing in it.
    """

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        cur.execute("DELETE FROM sales_request_items WHERE request_id = %s",
                    (self.request_id,))
        cur.execute("UPDATE sales_request SET items_count = 0 WHERE id = %s",
                    (self.request_id,))
        cur.close()

    def _row(self, actor):
        response = self._client_for(actor).get('/api/operations/requests')
        rows = {r['request_id']: r for r in response.get_json()['requests']}
        return rows.get(self.request_id)

    def test_a_request_with_no_items_has_nothing_pending(self):
        row = self._row(self.head)
        self.assertIsNotNone(row, 'the request went missing from the list')
        self.assertEqual(row['items_count'], 0)
        self.assertEqual(row['pending_items_count'], 0)
        self.assertEqual(row['costed_items_count'], 0)
        self.assertEqual(row['status'], 'No Items')

    def test_the_sales_list_agrees_that_nothing_is_uncosted(self):
        response = self._client_for(self.head).get('/api/sales/requests')
        rows = {r['request_id']: r for r in response.get_json()['requests']}
        row = rows.get(self.request_id)
        self.assertIsNotNone(row)
        self.assertEqual(row['approval_stats']['not_costed'], 0)


class CostingNotificationTest(_CostingHarness):
    """
    Every decision in the costing loop reaches the person it is about.

    None of these were sent. A member's price was declined and they found out
    by opening the page; a leader was never told a price had arrived, or that
    one had been sent again after a refusal. Notifications are disabled in the
    test run, so the calls are captured instead.
    """

    def setUp(self):
        super().setUp()
        self.sent = []
        self._real_notify = branding_gate.notify_users

        def capture(user_ids, title, content, link=None):
            self.sent.append({'to': sorted(int(u) for u in (user_ids or []) if u),
                              'title': title, 'content': content, 'link': link})
            return len(user_ids or [])

        branding_gate.notify_users = capture
        # notify_user() is a thin wrapper, so it has to be rebound with it.
        branding_gate.notify_user = (
            lambda user_id, title, content, link=None:
            capture([user_id], title, content, link=link))

    def tearDown(self):
        branding_gate.notify_users = self._real_notify
        branding_gate.notify_user = (
            lambda user_id, title, content, link=None:
            self._real_notify([user_id], title, content, link=link))
        super().tearDown()

    def _to(self, user_id):
        return [n for n in self.sent if n['to'] == [user_id]]

    def test_the_leader_is_told_a_price_has_arrived(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        self.sent = []
        self._propose(self.member, '120')
        told = self._to(self.leader)
        self.assertTrue(told, 'the leader who asked was not told: %s' % self.sent)
        self.assertIn('New costing to decide', told[0]['title'])
        self.assertIn('/operation_request?request=%d' % self.request_id, told[0]['link'])

    def test_the_author_is_told_their_price_was_declined_and_why(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        proposal_id = self._propose(self.member, '120').get_json()['proposal_id']
        self.sent = []
        self._client_for(self.leader).post(
            '/api/costing/proposals/%d/decide' % proposal_id,
            json={'decision': 'reject', 'note': 'Supplier quote is out of date'})
        told = self._to(self.member)
        self.assertTrue(told, 'the author was not told: %s' % self.sent)
        self.assertIn('declined', told[0]['title'].lower())
        self.assertIn('Supplier quote is out of date', told[0]['content'])

    def test_a_decline_with_no_reason_still_says_so(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        proposal_id = self._propose(self.member, '120').get_json()['proposal_id']
        self.sent = []
        self._client_for(self.leader).post(
            '/api/costing/proposals/%d/decide' % proposal_id, json={'decision': 'reject'})
        self.assertIn('No reason was given', self._to(self.member)[0]['content'])

    def test_a_second_price_after_a_refusal_reads_as_a_resubmission(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        proposal_id = self._propose(self.member, '120').get_json()['proposal_id']
        self._client_for(self.leader).post(
            '/api/costing/proposals/%d/decide' % proposal_id,
            json={'decision': 'reject', 'note': 'Too high'})
        self.sent = []
        response = self._propose(self.member, '95')
        self.assertTrue(response.get_json()['resubmission'])
        told = self._to(self.leader)
        self.assertTrue(told, 'the leader was not told about the new price: %s' % self.sent)
        self.assertIn('re-submitted', told[0]['title'].lower())

    def test_the_winner_and_the_losers_both_hear_the_outcome(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member, self.member_b])
        mine = self._propose(self.member, '120').get_json()['proposal_id']
        self._propose(self.member_b, '90')
        self.sent = []
        self._client_for(self.leader).post(
            '/api/costing/proposals/%d/decide' % mine, json={'decision': 'accept'})
        self.assertIn('accepted', self._to(self.member)[0]['title'].lower())
        losers = [n for n in self.sent if self.member_b in n['to']]
        self.assertTrue(losers, 'the other author was not told: %s' % self.sent)
        self.assertIn('Another price was accepted', losers[0]['content'])


class LockedItemTest(_CostingHarness):
    """
    A costed item is finished, and the page has to say so.

    The edit route protected costed items by skipping *every* item change on
    the request and returning "updated successfully" -- so an edit to the ten
    items that were still open was thrown away because the eleventh had been
    costed, and nothing said a word about it.
    """

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        cur.execute("SELECT client_id FROM sales_request WHERE id = %s", (self.request_id,))
        self.client_id = cur.fetchone()['client_id']
        cur.execute("""UPDATE sales_request_items
                       SET cost_per_item = 500, total_cost = 2000
                       WHERE id = %s""", (self.item_id,))
        cur.execute("""INSERT INTO sales_request_items (request_id, request_type, name, qty)
                       VALUES (%s, 'Booth', 'Still open', 3)""", (self.request_id,))
        self.open_item = cur.lastrowid
        cur.execute("UPDATE sales_request SET items_count = 2 WHERE id = %s",
                    (self.request_id,))
        cur.close()

    def _edit(self, items):
        return self._client_for(self.head).post(
            '/api/sales-requests/update-with-template/%d' % self.request_id,
            json={'title': 'Edited', 'client_id': self.client_id,
                  'start_date': '2026-09-10', 'end_date': '2026-09-12',
                  'template_instances': [{'instance_id': '1_Booth', 'template_id': 1,
                                          'request_type': 'Booth', 'fields': {},
                                          'items': items}]})

    def _items(self):
        cur = self._cursor()
        cur.execute("""SELECT name, qty, cost_per_item FROM sales_request_items
                       WHERE request_id = %s ORDER BY name""", (self.request_id,))
        rows = cur.fetchall()
        cur.close()
        return {r['name']: r for r in rows}

    def test_the_costed_item_keeps_its_cost_and_its_quantity(self):
        response = self._edit([
            {'name': 'Costing test item', 'quantity': 99},      # locked: changed
            {'name': 'Still open', 'quantity': 7},              # open: should take
        ])
        self.assertEqual(response.status_code, 200, response.get_json())
        items = self._items()
        self.assertEqual(float(items['Costing test item']['qty']), 4.0)
        self.assertEqual(float(items['Costing test item']['cost_per_item']), 500.0)

    def test_the_items_that_are_still_open_are_saved(self):
        # This is what used to be lost: one costed item froze the whole request.
        self._edit([
            {'name': 'Costing test item', 'quantity': 4},
            {'name': 'Still open', 'quantity': 7},
        ])
        self.assertEqual(float(self._items()['Still open']['qty']), 7.0)

    def test_the_caller_is_told_which_item_was_refused_and_why(self):
        body = self._edit([
            {'name': 'Costing test item', 'quantity': 99},
            {'name': 'Still open', 'quantity': 7},
        ]).get_json()
        refused = {e['name']: e for e in body.get('refused_changes', [])}
        self.assertIn('Costing test item', refused,
                      'the refusal was not reported: %s' % body)
        self.assertEqual(refused['Costing test item']['reason'], 'costed')
        self.assertIn('qty', refused['Costing test item']['changes'])
        self.assertIn('could not be changed', body['message'])

    def test_removing_a_costed_item_is_refused_and_said_so(self):
        body = self._edit([{'name': 'Still open', 'quantity': 3}]).get_json()
        refused = {e['name']: e for e in body.get('refused_changes', [])}
        self.assertIn('Costing test item', refused)
        self.assertEqual(refused['Costing test item']['changes'], ['removed'])
        self.assertIn('Costing test item', self._items())

    def test_an_edit_that_leaves_locked_items_alone_says_nothing_was_refused(self):
        body = self._edit([
            {'name': 'Costing test item', 'quantity': 4},
            {'name': 'Still open', 'quantity': 7},
        ]).get_json()
        self.assertEqual(body.get('refused_changes'), [])
        self.assertEqual(len(body.get('locked_items') or []), 1)

    def test_the_page_is_told_which_items_are_locked(self):
        items = self._client_for(self.head).get(
            '/api/sales/requests/%d' % self.request_id).get_json()['request']['items']
        by_name = {i['name']: i for i in items}
        self.assertTrue(by_name['Costing test item']['is_locked'])
        self.assertEqual(by_name['Costing test item']['lock_reason'], 'costed')
        self.assertFalse(by_name['Still open']['is_locked'])

    def test_a_priced_item_is_locked_too(self):
        cur = self._cursor()
        cur.execute("UPDATE sales_request_items SET sell_per_item = 900 WHERE id = %s",
                    (self.open_item,))
        cur.close()
        body = self._edit([
            {'name': 'Costing test item', 'quantity': 4},
            {'name': 'Still open', 'quantity': 99},
        ]).get_json()
        refused = {e['name']: e for e in body.get('refused_changes', [])}
        self.assertEqual(refused['Still open']['reason'], 'priced')


class RejectionReasonTest(_CostingHarness):
    """A decision reaches its author with the reason attached."""

    def test_the_author_is_told_why_it_was_rejected(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        proposal_id = self._propose(self.member, '120').get_json()['proposal_id']
        self._client_for(self.leader).post(
            '/api/costing/proposals/%d/decide' % proposal_id,
            json={'decision': 'reject', 'note': 'Supplier quote is out of date'})

        response = self._client_for(self.member).get(
            '/api/costing/request/%d' % self.request_id)
        items = response.get_json()['items']
        proposal = items[str(self.item_id)]['proposals'][0]
        self.assertEqual(proposal['status'], 'rejected')
        self.assertEqual(proposal['decision_note'], 'Supplier quote is out of date')

    def test_a_losing_proposal_says_so(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member, self.member_b])
        mine = self._propose(self.member, '120').get_json()['proposal_id']
        theirs = self._propose(self.member_b, '90').get_json()['proposal_id']
        self._client_for(self.leader).post(
            '/api/costing/proposals/%d/decide' % theirs, json={'decision': 'accept'})

        response = self._client_for(self.member).get(
            '/api/costing/request/%d' % self.request_id)
        by_id = {p['id']: p for p in
                 response.get_json()['items'][str(self.item_id)]['proposals']}
        self.assertEqual(by_id[mine]['decision_note'], 'Another proposal was accepted')


# A one-pixel PNG, so the upload path is exercised with a real image.
_PNG = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00'
        b'\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\n'
        b'IDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00'
        b'\x00IEND\xaeB`\x82')


class AlternativeOptionTest(_CostingHarness):
    """Costing's second way of doing an item, against the item itself."""

    def tearDown(self):
        # The database rolls back; the uploaded file does not. Left alone these
        # pile up under uploads/alternatives as rows that no longer exist.
        import os
        for path in getattr(self, 'uploaded', []):
            try:
                os.remove(path.lstrip('/'))
                os.rmdir(os.path.dirname(path.lstrip('/')))
            except OSError:
                pass
        super().tearDown()

    def _add(self, actor, comment='Aluminium instead of steel', label='Aluminium',
             filename='alt.png', payload=_PNG):
        import io as _io
        response = self._client_for(actor).post(
            '/api/costing/items/%d/alternatives' % self.item_id,
            data={'comment': comment, 'label': label,
                  'image': (_io.BytesIO(payload), filename)},
            content_type='multipart/form-data')
        body = response.get_json() or {}
        if body.get('image_url'):
            self.uploaded = getattr(self, 'uploaded', []) + [body['image_url']]
        return response

    def _alternatives(self, actor):
        response = self._client_for(actor).get(
            '/api/costing/items/%d/alternatives' % self.item_id)
        self.assertEqual(response.status_code, 200)
        return response.get_json()['alternatives']

    def test_costing_offers_an_alternative_and_everyone_sees_it(self):
        self._assign(self.head, [self.leader])
        self._assign(self.leader, [self.member])
        response = self._add(self.member)
        self.assertEqual(response.status_code, 200, response.get_json())

        rows = self._alternatives(self.head)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['label'], 'Aluminium')
        self.assertEqual(rows[0]['comment'], 'Aluminium instead of steel')
        self.assertTrue(rows[0]['image_url'].startswith('/uploads/alternatives/'))

    def test_a_picture_with_no_word_about_it_is_refused(self):
        response = self._add(self.member, comment='')
        self.assertEqual(response.status_code, 400)
        self.assertIn('what the alternative is', response.get_json()['error'])

    def test_only_images_are_accepted(self):
        response = self._add(self.member, filename='quote.pdf', payload=b'%PDF-1.4')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Images only', response.get_json()['error'])

    def test_an_alternative_is_not_an_attachment(self):
        # Same table, different thing: it must not appear as something sales
        # attached, or the item reads as having two specifications.
        self._add(self.leader)
        response = self._client_for(self.head).get(
            '/api/operations/requests/%d' % self.request_id)
        item = [i for i in response.get_json()['request']['items']
                if i['id'] == self.item_id][0]
        self.assertEqual(item['attachments'], [])
        self.assertEqual(len(item['alternatives']), 1)
        self.assertEqual(item['alternatives'][0]['label'], 'Aluminium')

    def test_whoever_put_it_up_can_take_it_down(self):
        alternative_id = self._add(self.leader).get_json()['id']
        response = self._client_for(self.leader).delete(
            '/api/costing/alternatives/%d' % alternative_id)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self._alternatives(self.head), [])

    def test_somebody_else_cannot_take_it_down(self):
        alternative_id = self._add(self.member).get_json()['id']
        response = self._client_for(self.member_b).delete(
            '/api/costing/alternatives/%d' % alternative_id)
        self.assertEqual(response.status_code, 403)

    def test_the_head_can_take_any_of_them_down(self):
        alternative_id = self._add(self.member).get_json()['id']
        response = self._client_for(self.head).delete(
            '/api/costing/alternatives/%d' % alternative_id)
        self.assertEqual(response.status_code, 200, response.get_json())

    def test_sales_cannot_offer_one(self):
        sales = self._make_user('cost-sales', 'sales_member', None)
        self.assertEqual(self._add(sales).status_code, 403)


if __name__ == '__main__':
    unittest.main()
