"""
Quarterly targets: the arithmetic on its own, and the cascade end to end.

The DB half follows the harness in test_scope.py -- a real connection with
autocommit off, branding_gate.connection monkeypatched to hand out a wrapper
whose commit() is a no-op, and a rollback in tearDown. Nothing survives.
"""

import unittest
from datetime import date
from decimal import Decimal

import MySQLdb
import MySQLdb.cursors

import branding_gate
import targets


class TargetArithmeticTest(unittest.TestCase):
    """The rules, with no database in sight."""

    def test_self_check_passes(self):
        targets.demo()

    def test_period_parsing_rejects_rubbish(self):
        self.assertEqual(targets.parse_period('2026-q3'), (2026, 3))
        for bad in ('2026', '2026-Q5', 'Q3', '', None, '2026-Q0', 'abcd-Q1'):
            with self.assertRaises(targets.InvalidPeriod):
                targets.parse_period(bad)

    def test_quarter_bounds_cover_the_whole_quarter(self):
        self.assertEqual(targets.period_bounds('2026-Q1'),
                         (date(2026, 1, 1), date(2026, 3, 31)))
        self.assertEqual(targets.period_bounds('2026-Q4'),
                         (date(2026, 10, 1), date(2026, 12, 31)))

    def test_an_uneven_split_is_allowed(self):
        million = Decimal('1000000')
        self.assertIsNone(targets.validate_assignment(
            Decimal('200000'), million, targets.ZERO))
        self.assertIsNone(targets.validate_assignment(
            Decimal('800000'), million, Decimal('200000')))

    def test_the_children_may_not_outgrow_the_parent(self):
        million = Decimal('1000000')
        error = targets.validate_assignment(
            Decimal('800001'), million, Decimal('200000'))
        self.assertIsNotNone(error)
        self.assertIn('800,000.00', error)

    def test_a_remainder_may_be_left_unassigned(self):
        self.assertIsNone(targets.validate_assignment(
            Decimal('500000'), Decimal('1000000'), Decimal('200000')))

    def test_the_top_of_the_tree_is_uncapped(self):
        self.assertIsNone(targets.validate_assignment(
            Decimal('9999999'), None, targets.ZERO))

    def test_a_manager_cannot_be_cut_below_what_they_handed_down(self):
        error = targets.validate_assignment(
            Decimal('100000'), Decimal('1000000'), targets.ZERO,
            child_committed=Decimal('300000'))
        self.assertIsNotNone(error)
        self.assertIn('300,000.00', error)

    def test_amounts_are_parsed_strictly(self):
        self.assertEqual(targets.to_amount('1,000,000'), Decimal('1000000.00'))
        self.assertEqual(targets.to_amount(' 250000.50 '), Decimal('250000.50'))
        for bad in ('-1', 'lots', '', None, 'NaN'):
            with self.assertRaises(ValueError):
                targets.to_amount(bad)

    def test_the_tree_rolls_achievement_up_the_line(self):
        people = [
            {'id': 1, 'name': 'Head', 'manager_id': None},
            {'id': 2, 'name': 'Leader', 'manager_id': 1},
            {'id': 3, 'name': 'Member', 'manager_id': 2},
        ]
        rows = targets.build_tree(
            people,
            {1: Decimal('1000'), 2: Decimal('600')},
            {3: Decimal('40'), 2: Decimal('10'), 1: Decimal('5')},
        )
        head, leader, member = rows
        self.assertEqual(head['team_achieved'], Decimal('55'))
        self.assertEqual(leader['team_achieved'], Decimal('50'))
        self.assertEqual(member['team_achieved'], Decimal('40'))
        self.assertEqual(head['assigned'], Decimal('600'))
        self.assertEqual(head['unassigned'], Decimal('400'))
        # A member has no reports, so nothing is handed down and none is spare.
        self.assertEqual(member['assigned'], targets.ZERO)
        self.assertIsNone(member['target'])
        self.assertIsNone(member['unassigned'])

    def test_a_narrowed_view_reroots_the_tree(self):
        people = [
            {'id': 1, 'name': 'Head', 'manager_id': None},
            {'id': 2, 'name': 'Leader', 'manager_id': 1},
            {'id': 3, 'name': 'Member', 'manager_id': 2},
        ]
        rows = targets.build_tree(people, {}, {}, visible_ids=[3])
        self.assertEqual([r['id'] for r in rows], [3])
        self.assertEqual(rows[0]['depth'], 0)


class _RollbackConnection:
    def __init__(self, raw_connection):
        self.raw_connection = raw_connection

    def commit(self):
        pass

    def close(self):
        pass

    def rollback(self):
        self.raw_connection.rollback()


class TargetCascadeTest(unittest.TestCase):
    """CEO -> Sales Head -> two team leaders -> members, over the real routes."""

    PERIOD = '2026-Q3'

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
        cur.execute("SELECT id FROM department WHERE code = 'sales'")
        self.department_id = cur.fetchone()["id"]
        self.roles = {}
        for code in ("admin", "sales_head", "sales_team_leader", "sales_member"):
            cur.execute("SELECT id FROM rbac_role WHERE code = %s", (code,))
            self.roles[code] = cur.fetchone()["id"]
        cur.close()

        self.ceo = self._make_user("tgt-ceo", "admin", None)
        self.head = self._make_user("tgt-head", "sales_head", self.ceo)
        self.leader_a = self._make_user("tgt-leader-a", "sales_team_leader", self.head)
        self.leader_b = self._make_user("tgt-leader-b", "sales_team_leader", self.head)
        self.member_a = self._make_user("tgt-member-a", "sales_member", self.leader_a)
        self.member_b = self._make_user("tgt-member-b", "sales_member", self.leader_b)

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
            VALUES (%s, %s, %s, 'x', %s, 'Target Test', %s, %s, %s, NOW())
            """,
            (username, '018%08d' % (abs(hash(username)) % 10**8),
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

    def _assign(self, actor, user_id, amount):
        return self._client_for(actor).post(
            '/api/targets/assign',
            json={'user_id': user_id, 'period': self.PERIOD, 'amount': amount},
        )

    def _rows_for(self, user_id):
        response = self._client_for(user_id).get(
            '/api/targets?period=' + self.PERIOD)
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload.get('success'), payload)
        return {row['id']: row for row in payload['rows']}

    # -- the cascade --------------------------------------------------------

    def test_the_brief_cascade_works_end_to_end(self):
        self.assertEqual(self._assign(self.ceo, self.head, '1000000').status_code, 200)
        # Deliberately uneven, in the numbers from the brief.
        self.assertEqual(self._assign(self.head, self.leader_a, '200000').status_code, 200)
        self.assertEqual(self._assign(self.head, self.leader_b, '800000').status_code, 200)
        self.assertEqual(self._assign(self.leader_a, self.member_a, '150000').status_code, 200)

        rows = self._rows_for(self.head)
        self.assertEqual(rows[self.head]['target'], 1000000.0)
        self.assertEqual(rows[self.head]['assigned'], 1000000.0)
        self.assertEqual(rows[self.head]['unassigned'], 0.0)
        self.assertEqual(rows[self.leader_a]['target'], 200000.0)
        self.assertEqual(rows[self.leader_a]['unassigned'], 50000.0)
        self.assertEqual(rows[self.leader_b]['target'], 800000.0)

    def test_a_manager_cannot_hand_out_more_than_they_hold(self):
        self._assign(self.ceo, self.head, '1000000')
        self._assign(self.head, self.leader_a, '200000')
        response = self._assign(self.head, self.leader_b, '800001')
        self.assertEqual(response.status_code, 400)
        self.assertIn('left to assign', response.get_json()['error'])

    def test_a_remainder_may_be_left_unassigned(self):
        self._assign(self.ceo, self.head, '1000000')
        self._assign(self.head, self.leader_a, '200000')
        self.assertEqual(self._assign(self.head, self.leader_b, '300000').status_code, 200)
        rows = self._rows_for(self.head)
        self.assertEqual(rows[self.head]['unassigned'], 500000.0)

    def test_a_target_cannot_be_cut_below_what_is_already_distributed(self):
        self._assign(self.ceo, self.head, '1000000')
        self._assign(self.head, self.leader_a, '200000')
        self._assign(self.leader_a, self.member_a, '150000')
        response = self._assign(self.head, self.leader_a, '100000')
        self.assertEqual(response.status_code, 400)
        self.assertIn('already distributed', response.get_json()['error'])

    def test_only_the_direct_manager_may_set_a_target(self):
        self._assign(self.ceo, self.head, '1000000')
        self._assign(self.head, self.leader_a, '200000')
        # A leader may see their peer's member under department-free team scope?
        # No: they may not set anyone but their own reports.
        response = self._assign(self.leader_a, self.member_b, '10000')
        self.assertEqual(response.status_code, 403)

    def test_a_member_cannot_set_their_own_target(self):
        response = self._assign(self.member_a, self.member_a, '999')
        self.assertEqual(response.status_code, 403)

    def test_a_negative_target_is_refused(self):
        response = self._assign(self.ceo, self.head, '-5')
        self.assertEqual(response.status_code, 400)

    def test_an_amount_typed_with_separators_is_accepted(self):
        # The page groups digits as they are typed; the value posted keeps the
        # commas, so the route has to take them.
        response = self._assign(self.ceo, self.head, '1,000,000')
        self.assertEqual(response.status_code, 200, response.get_json())
        rows = self._rows_for(self.head)
        self.assertEqual(rows[self.head]['target'], 1000000.0)

    # -- the flow, and who set what -----------------------------------------

    def test_a_row_names_who_set_the_number_and_when(self):
        self._assign(self.ceo, self.head, '1000000')
        rows = self._rows_for(self.head)
        self.assertEqual(rows[self.head]['set_by'], 'tgt-ceo')
        self.assertTrue(rows[self.head]['set_on'])
        # Nobody set the leaders' yet, so there is nothing to attribute.
        self.assertIsNone(rows[self.leader_a]['set_by'])

    def test_manager_id_is_dropped_when_the_manager_is_out_of_scope(self):
        # The flow grid roots a branch wherever the chain leaves the caller's
        # scope; a manager_id pointing at somebody invisible would orphan it.
        rows = self._rows_for(self.leader_a)
        self.assertIsNone(rows[self.leader_a]['manager_id'])
        self.assertEqual(rows[self.member_a]['manager_id'], self.leader_a)

    # -- the PDF export -----------------------------------------------------

    def _pdf(self, actor, query):
        return self._client_for(actor).get('/api/targets/pdf?' + query)

    def test_the_quarter_export_is_a_pdf(self):
        self._assign(self.ceo, self.head, '1000000')
        self._assign(self.head, self.leader_a, '200000')
        response = self._pdf(self.head, 'period=' + self.PERIOD)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'application/pdf')
        self.assertTrue(response.data.startswith(b'%PDF'))
        self.assertIn(self.PERIOD, response.headers['Content-Disposition'])

    def test_the_year_export_covers_the_whole_year(self):
        self._assign(self.ceo, self.head, '1000000')
        response = self._pdf(self.head, 'year=2026')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.startswith(b'%PDF'))
        self.assertIn('2026', response.headers['Content-Disposition'])

    def test_an_export_holds_only_what_the_caller_may_see(self):
        # A bigger scope must produce a bigger document; the member's export is
        # one person, the head's is the department.
        self._assign(self.ceo, self.head, '1000000')
        self._assign(self.head, self.leader_a, '200000')
        self._assign(self.leader_a, self.member_a, '150000')
        head = self._pdf(self.head, 'period=' + self.PERIOD)
        member = self._pdf(self.member_a, 'period=' + self.PERIOD)
        self.assertEqual(head.status_code, 200)
        self.assertEqual(member.status_code, 200)
        self.assertLess(len(member.data), len(head.data))

    def test_a_rubbish_period_is_refused_by_the_export(self):
        response = self._pdf(self.head, 'period=nonsense')
        self.assertEqual(response.status_code, 400)

    # -- the year view ------------------------------------------------------

    def _year_rows(self, user_id, year=2026):
        response = self._client_for(user_id).get('/api/targets/year?year=%d' % year)
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload.get('success'), payload)
        return payload, {row['id']: row for row in payload['rows']}

    def test_the_year_view_holds_one_column_per_quarter(self):
        self._assign(self.ceo, self.head, '1000000')
        payload, rows = self._year_rows(self.head)
        self.assertEqual(payload['periods'],
                         ['2026-Q1', '2026-Q2', '2026-Q3', '2026-Q4'])
        head = rows[self.head]
        self.assertEqual(head['quarters']['2026-Q3']['target'], 1000000.0)
        self.assertIsNone(head['quarters']['2026-Q1']['target'])
        self.assertEqual(head['year_target'], 1000000.0)

    def test_the_year_view_sums_every_quarter_set(self):
        self._assign(self.ceo, self.head, '1000000')
        self._client_for(self.ceo).post('/api/targets/assign', json={
            'user_id': self.head, 'period': '2026-Q4', 'amount': '250000'})
        _, rows = self._year_rows(self.head)
        self.assertEqual(rows[self.head]['year_target'], 1250000.0)

    def test_the_year_view_agrees_with_the_quarter_view(self):
        self._assign(self.ceo, self.head, '1000000')
        self._assign(self.head, self.leader_a, '200000')
        quarter = self._rows_for(self.head)
        _, year = self._year_rows(self.head)
        for person in (self.head, self.leader_a):
            self.assertEqual(year[person]['quarters']['2026-Q3']['target'],
                             quarter[person]['target'])
            self.assertEqual(year[person]['quarters']['2026-Q3']['achieved'],
                             quarter[person]['team_achieved'])

    def test_the_year_view_is_scoped_like_the_quarter_view(self):
        _, rows = self._year_rows(self.member_a)
        self.assertEqual(list(rows), [self.member_a])
        _, leader_rows = self._year_rows(self.leader_a)
        self.assertIn(self.member_a, leader_rows)
        self.assertNotIn(self.member_b, leader_rows)
        self.assertNotIn(self.head, leader_rows)

    def test_a_rubbish_year_is_refused(self):
        response = self._client_for(self.head).get('/api/targets/year?year=nope')
        self.assertEqual(response.status_code, 400)

    # -- who sees what ------------------------------------------------------

    def test_a_member_sees_only_themselves(self):
        self._assign(self.ceo, self.head, '1000000')
        self._assign(self.head, self.leader_a, '200000')
        self._assign(self.leader_a, self.member_a, '150000')
        rows = self._rows_for(self.member_a)
        self.assertIn(self.member_a, rows)
        for other in (self.head, self.leader_a, self.leader_b, self.member_b):
            self.assertNotIn(other, rows)
        self.assertFalse(rows[self.member_a]['can_assign'])

    def test_a_team_leader_sees_their_team_and_no_further(self):
        self._assign(self.ceo, self.head, '1000000')
        self._assign(self.head, self.leader_a, '200000')
        rows = self._rows_for(self.leader_a)
        self.assertIn(self.leader_a, rows)
        self.assertIn(self.member_a, rows)
        self.assertNotIn(self.member_b, rows)
        self.assertNotIn(self.head, rows)
        # They may set their own report's number, but not their own.
        self.assertTrue(rows[self.member_a]['can_assign'])
        self.assertFalse(rows[self.leader_a]['can_assign'])

    def test_the_head_sees_the_whole_department(self):
        rows = self._rows_for(self.head)
        for person in (self.head, self.leader_a, self.leader_b,
                       self.member_a, self.member_b):
            self.assertIn(person, rows)

    def test_a_member_may_not_reach_the_assign_route_at_all(self):
        response = self._client_for(self.member_a).post(
            '/api/targets/assign',
            json={'user_id': self.member_b, 'period': self.PERIOD, 'amount': '1'})
        self.assertEqual(response.status_code, 403)

    # -- teams --------------------------------------------------------------

    def test_naming_a_team_shows_it_against_the_leader(self):
        name = 'Target Test Team A'
        response = self._client_for(self.head).post(
            '/api/teams/name', json={'leader_id': self.leader_a, 'team_name': name})
        self.assertEqual(response.status_code, 200, response.get_json())
        rows = self._rows_for(self.head)
        self.assertEqual(rows[self.leader_a]['team_name'], name)
        self.assertIsNone(rows[self.member_a]['team_name'])

    def test_a_team_needs_somebody_in_it(self):
        response = self._client_for(self.head).post(
            '/api/teams/name', json={'leader_id': self.member_a, 'team_name': 'Nobody'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('nobody reporting', response.get_json()['error'])

    def test_a_team_leader_may_not_name_teams(self):
        response = self._client_for(self.leader_a).post(
            '/api/teams/name', json={'leader_id': self.leader_a, 'team_name': 'Mine'})
        self.assertEqual(response.status_code, 403)


class TargetPolicyTest(unittest.TestCase):
    """The grant matrix says what the brief says."""

    def test_the_sales_ladder_reads_at_its_own_level(self):
        import rbac
        self.assertEqual(rbac.SEED_MATRIX['sales_head']['target.view'], 'department')
        self.assertEqual(rbac.SEED_MATRIX['sales_team_leader']['target.view'], 'team')
        self.assertEqual(rbac.SEED_MATRIX['sales_member']['target.view'], 'own')

    def test_a_member_holds_no_power_to_assign(self):
        import rbac
        self.assertNotIn('target.assign', rbac.SEED_MATRIX['sales_member'])

    def test_only_the_head_and_admin_name_teams(self):
        import rbac
        namers = [code for code, grants in rbac.SEED_MATRIX.items()
                  if 'team.edit' in grants]
        self.assertEqual(sorted(namers), ['admin', 'sales_head'])


if __name__ == '__main__':
    unittest.main()
