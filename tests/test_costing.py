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


class CostingChainTest(unittest.TestCase):
    """Head -> leaders -> members -> proposals -> one accepted, over the routes."""

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
        cur.execute("SELECT id FROM client ORDER BY id LIMIT 1")
        client_id = cur.fetchone()["id"]

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

    # -- the chain ----------------------------------------------------------

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

    def test_direct_costing_is_closed_to_the_ladder(self):
        payload = {'request_id': self.request_id,
                   'items': [{'id': self.item_id, 'cost_per_item': 5}]}
        for actor in (self.leader, self.member):
            response = self._client_for(actor).post(
                '/api/operations/requests/add-costs', json=payload)
            self.assertEqual(response.status_code, 403)
        # The Head keeps the override.
        self.assertEqual(
            self._client_for(self.head).post(
                '/api/operations/requests/add-costs', json=payload).status_code,
            200)


if __name__ == '__main__':
    unittest.main()
