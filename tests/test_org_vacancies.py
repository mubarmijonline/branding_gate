"""
Vacant positions on the org chart. A person under an empty seat keeps a real
manager (the nearest person above it); filling the seat moves everything
under it to the new person. Rolled back like test_costing.py.
"""

import unittest

import branding_gate
from test_costing import _CostingHarness


class VacancyTest(_CostingHarness):

    def _admin(self):
        cur = self._cursor()
        cur.execute("SELECT id FROM rbac_role WHERE code = 'admin'")
        role_id = cur.fetchone()['id']
        cur.execute("""INSERT INTO user (name, mobile, email, password, username, title,
                                         department_id, rbac_role_id, manager_id, date)
                       VALUES ('vac-admin', '01099999991', 'va@example.com', 'x', 'vac-admin',
                               'Admin', %s, %s, %s, NOW())""", (self.department_id, role_id, self.head))
        user_id = cur.lastrowid
        cur.close()
        return user_id

    def _form(self, user_id, **extra):
        cur = self._cursor()
        cur.execute("SELECT name, email, username, title FROM user WHERE id = %s", (user_id,))
        u = dict(cur.fetchone())
        cur.close()
        u['mobile'] = '0101%07d' % (user_id % 10**7)
        u.update(extra)
        return u

    def _user(self, user_id):
        cur = self._cursor()
        cur.execute("SELECT manager_id, reports_to_vacancy_id, rbac_role_id, is_active FROM user WHERE id = %s",
                    (user_id,))
        row = cur.fetchone()
        cur.close()
        return row

    def _seat(self, admin, role_code, reports_to):
        r = self._client_for(admin).post('/api/org/vacancies', json={
            'rbac_role_id': self.roles[role_code], 'reports_to': reports_to})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()['id']

    def _place(self, admin, user_id, manager):
        return self._client_for(admin).post('/api/users/edit/%d' % user_id, json=self._form(
            user_id, rbac_role_id=self.roles['operations_member'], manager_id=manager))

    def test_under_an_empty_seat_the_manager_is_the_person_above_it(self):
        admin = self._admin()
        seat = self._seat(admin, 'operations_team_leader', self.head)
        self.assertEqual(self._place(admin, self.member, 'v:%d' % seat).status_code, 200)
        row = self._user(self.member)
        self.assertEqual(row['manager_id'], self.head)
        self.assertEqual(row['reports_to_vacancy_id'], seat)
        # Chains of empty seats resolve too.
        lower = self._seat(admin, 'operations_member', 'v:%d' % seat)
        self.assertEqual(branding_gate.vacancy_manager(self._cursor(), lower), self.head)

    def test_filling_the_seat_moves_its_people_under_the_new_person(self):
        admin = self._admin()
        seat = self._seat(admin, 'operations_team_leader', self.head)
        self._place(admin, self.member, 'v:%d' % seat)
        r = self._client_for(admin).post('/api/org/vacancies/%d/fill' % seat, json={'user_id': self.leader_b})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self._user(self.member)['manager_id'], self.leader_b)
        self.assertIsNone(self._user(self.member)['reports_to_vacancy_id'])
        self.assertEqual(self._user(self.leader_b)['manager_id'], self.head)
        self.assertEqual(self._user(self.leader_b)['rbac_role_id'], self.roles['operations_team_leader'])

    def test_removing_a_seat_moves_its_people_up(self):
        admin = self._admin()
        top = self._seat(admin, 'operations_team_leader', self.head)
        self._place(admin, self.member, 'v:%d' % top)
        self.assertEqual(self._client_for(admin).delete('/api/org/vacancies/%d' % top).status_code, 200)
        row = self._user(self.member)
        self.assertIsNone(row['reports_to_vacancy_id'])
        self.assertEqual(row['manager_id'], self.head)

    def test_a_seat_must_sit_under_someone_more_senior(self):
        admin = self._admin()
        r = self._client_for(admin).post('/api/org/vacancies', json={
            'rbac_role_id': self.roles['operations_manager'], 'reports_to': self.member})
        self.assertEqual(r.status_code, 400)

    def test_switching_someone_off(self):
        admin = self._admin()
        r = self._client_for(admin).post('/api/users/edit/%d' % self.member,
                                         json=self._form(self.member, is_active=False))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self._user(self.member)['is_active'], 0)


if __name__ == '__main__':
    unittest.main()


class InactiveHoldsNothingTest(_CostingHarness):
    def test_a_switched_off_account_holds_no_permissions(self):
        self.assertTrue(branding_gate.load_permissions(self.member)[0])
        cur = self._cursor()
        cur.execute("UPDATE user SET is_active = 0 WHERE id = %s", (self.member,))
        cur.close()
        self.assertEqual(branding_gate.load_permissions(self.member), ({}, None))
