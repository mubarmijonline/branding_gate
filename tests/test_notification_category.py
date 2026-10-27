"""Important (something waits on the reader) versus Announcement."""

import unittest

import branding_gate

IMPORTANT = [
    'Approval Needed',
    'New Sales Request #018921',
    'Request #018921 Costing Completed',
    'Request #018921 Re-Costing Completed',
    'Costing assigned: 3 item(s)',
    'New costing to decide: booth',
    'Costing re-submitted: booth',
    'Re-costing needed: screen',
    'Re-pricing needed: screen',
    'Negotiation to review: screen',
    'Client approved: Stage 3x4',
    'Invoice to post: EVA pharma',
    'Invoice returned: SR-784',
    'Expenses to approve: Azer Atef',
    'عهدة request from Ayman Nagy',
    'عهدة request: David Osama',
    'عهدة request approved by Haitham Fouad',
    'تسوية عهدة from Azer Atef',
    'New supplier request: Steps',
    'New client request: tadros',
    'Out of stock: كرسي',
    'Below minimum: كرسي',
    'Mariam Magdy mentioned you: request #18921',
]
ANNOUNCEMENT = [
    'Request Approved', 'Request Rejected', 'Sales Request #018921 Updated',
    'Costing accepted: booth', 'Costing declined: booth', 'Costing closed: booth',
    'New supplier added: Steps', 'Supplier added: Steps', 'Supplier request declined',
    'Invoice 12 posted', 'Balance approved: EGP 1,000.00', 'Your عهدة request went to Finance',
    'Balance request withdrawn: REQ-1', 'New comment on request #784', '',
]


class NotificationCategoryTest(unittest.TestCase):

    def test_work_is_important(self):
        for title in IMPORTANT:
            self.assertEqual(branding_gate.notification_category(title), 'important', title)

    def test_news_is_an_announcement(self):
        for title in ANNOUNCEMENT:
            self.assertEqual(branding_gate.notification_category(title), 'announcement', title)


if __name__ == '__main__':
    unittest.main()


class BystanderTest(unittest.TestCase):
    """An admin on a desk's fan-out is told, but it is not waiting on them."""

    def test_admins_are_fyi_where_another_desk_holds_the_work(self):
        audience = branding_gate.users_holding('user_balance.approve')
        conn, cur = branding_gate.connection()
        try:
            admins = branding_gate._admin_ids(cur, list(audience))
        finally:
            cur.close()
            conn.close()
        self.assertEqual(set(audience.fyi), admins)

    def test_admin_only_work_stays_theirs(self):
        audience = branding_gate.users_holding('party_request.approve_admin', include_root=True)
        self.assertEqual(audience.fyi, frozenset())
        self.assertEqual(branding_gate.get_users_by_role('admin').fyi, frozenset())

    def test_the_marks_survive_being_added_to(self):
        audience = branding_gate.Audience.of([1, 2], {2})
        self.assertEqual(([9] + audience).fyi, frozenset({2}))
        self.assertEqual((audience + [9]).fyi, frozenset({2}))
        self.assertEqual(sorted([9] + audience), [1, 2, 9])
