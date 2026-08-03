"""
Tests for the department / role / manager assignment helpers.

_validate_hierarchy is what stops the org chart becoming unusable: a manager
who is not senior to their report, or a reporting cycle, would both break team
scope resolution at query time.
"""

import unittest

import branding_gate


class _ScriptedCursor:
    """Returns canned rows in order, so no database is needed."""

    def __init__(self, results):
        self._results = list(results)
        self.queries = []

    def execute(self, sql, params=None):
        self.queries.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self._results.pop(0) if self._results else None


class HierarchyFieldsTest(unittest.TestCase):
    def test_absent_keys_are_not_returned(self):
        fields, error = branding_gate._hierarchy_fields({'name': 'X'})
        self.assertIsNone(error)
        self.assertEqual(fields, {})

    def test_present_keys_are_coerced_to_int(self):
        fields, error = branding_gate._hierarchy_fields(
            {'department_id': '3', 'rbac_role_id': 7, 'manager_id': '1'}
        )
        self.assertIsNone(error)
        self.assertEqual(fields, {'department_id': 3, 'rbac_role_id': 7, 'manager_id': 1})

    def test_blank_values_clear_the_field(self):
        for blank in ('', None, 'undefined', 'null'):
            with self.subTest(blank=blank):
                fields, error = branding_gate._hierarchy_fields({'manager_id': blank})
                self.assertIsNone(error)
                self.assertEqual(fields, {'manager_id': None})

    def test_a_non_numeric_value_is_rejected(self):
        fields, error = branding_gate._hierarchy_fields({'rbac_role_id': 'sales_head'})
        self.assertIsNone(fields)
        self.assertIn('rbac_role_id', error)


class ValidateHierarchyTest(unittest.TestCase):
    def test_nothing_to_validate_passes(self):
        self.assertIsNone(branding_gate._validate_hierarchy(_ScriptedCursor([]), {}))

    def test_an_unknown_role_is_rejected(self):
        cur = _ScriptedCursor([None])
        self.assertEqual(
            branding_gate._validate_hierarchy(cur, {'rbac_role_id': 99}),
            'Unknown role',
        )

    def test_a_user_cannot_report_to_themselves(self):
        cur = _ScriptedCursor([])
        self.assertEqual(
            branding_gate._validate_hierarchy(cur, {'manager_id': 5}, user_id=5),
            'A user cannot report to themselves',
        )

    def test_an_unknown_manager_is_rejected(self):
        cur = _ScriptedCursor([None])
        self.assertEqual(
            branding_gate._validate_hierarchy(cur, {'manager_id': 42}),
            'Unknown manager',
        )

    def test_a_manager_must_outrank_their_report(self):
        # role lookup, manager level, own level
        cur = _ScriptedCursor([
            {'id': 6, 'level': 2, 'department_id': 1},
            {'level': 2},
            {'level': 2},
        ])
        self.assertEqual(
            branding_gate._validate_hierarchy(cur, {'rbac_role_id': 6, 'manager_id': 9}),
            'A manager must hold a more senior role than their report',
        )

    def test_a_senior_manager_is_accepted(self):
        cur = _ScriptedCursor([
            {'id': 6, 'level': 3, 'department_id': 1},   # role lookup
            {'level': 1},                                # manager level
            {'level': 3},                                # own level
        ])
        self.assertIsNone(
            branding_gate._validate_hierarchy(cur, {'rbac_role_id': 6, 'manager_id': 9})
        )

    def test_a_reporting_cycle_is_refused(self):
        # No role given, so validation goes straight to the cycle walk:
        # manager lookup, then 9 -> 5 which is the user being edited.
        cur = _ScriptedCursor([
            {'level': 1},          # manager 9 exists
            {'manager_id': 5},     # 9 reports to 5, the user we are editing
        ])
        self.assertEqual(
            branding_gate._validate_hierarchy(cur, {'manager_id': 9}, user_id=5),
            'That manager would create a reporting cycle',
        )

    def test_a_clean_reporting_line_is_accepted(self):
        cur = _ScriptedCursor([
            {'level': 1},          # manager 9 exists
            {'manager_id': None},  # 9 reports to nobody
        ])
        self.assertIsNone(
            branding_gate._validate_hierarchy(cur, {'manager_id': 9}, user_id=5)
        )


if __name__ == '__main__':
    unittest.main()
