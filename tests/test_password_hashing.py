import inspect
import unittest

from werkzeug.security import generate_password_hash

import branding_gate


class _FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))


class _FakeConnection:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


class PasswordVerificationTest(unittest.TestCase):
    """verify_password must accept hashed rows and upgrade legacy plaintext ones."""

    def _verify(self, stored, submitted):
        cur, conn = _FakeCursor(), _FakeConnection()
        ok = branding_gate.verify_password({"id": 42, "password": stored}, submitted, conn, cur)
        upgraded = bool(cur.calls) and "UPDATE user SET password" in cur.calls[0][0]
        return ok, upgraded, cur, conn

    def test_hashed_password_is_accepted_without_being_rewritten(self):
        ok, upgraded, _, conn = self._verify(generate_password_hash("correct"), "correct")
        self.assertTrue(ok)
        self.assertFalse(upgraded)
        self.assertEqual(conn.commits, 0)

    def test_hashed_password_rejects_a_wrong_password(self):
        ok, upgraded, _, _ = self._verify(generate_password_hash("correct"), "wrong")
        self.assertFalse(ok)
        self.assertFalse(upgraded)

    def test_legacy_plaintext_row_is_upgraded_to_a_hash_on_success(self):
        ok, upgraded, cur, conn = self._verify("correct", "correct")
        self.assertTrue(ok)
        self.assertTrue(upgraded)
        self.assertEqual(conn.commits, 1)

        new_hash, user_id = cur.calls[0][1]
        self.assertEqual(user_id, 42)
        self.assertTrue(new_hash.startswith(branding_gate.PASSWORD_HASH_PREFIXES))
        self.assertTrue(branding_gate.check_password_hash(new_hash, "correct"))

    def test_legacy_plaintext_row_is_not_upgraded_on_failure(self):
        ok, upgraded, _, conn = self._verify("correct", "wrong")
        self.assertFalse(ok)
        self.assertFalse(upgraded)
        self.assertEqual(conn.commits, 0)

    def test_empty_submitted_password_never_authenticates(self):
        for stored in ("correct", "", generate_password_hash("correct")):
            with self.subTest(stored=stored[:12]):
                ok, upgraded, _, _ = self._verify(stored, "")
                self.assertFalse(ok)
                self.assertFalse(upgraded)


class PasswordExposureTest(unittest.TestCase):
    """The users API and its template must never carry a password to the client."""

    def test_users_api_handler_never_selects_or_returns_the_password(self):
        source = inspect.getsource(branding_gate.get_users.__wrapped__)
        self.assertNotIn("u.password", source)
        self.assertNotIn("user['password']", source)

    def test_users_template_has_no_password_column(self):
        with branding_gate.app.test_request_context("/"):
            branding_gate.session["user_id"] = 1
            branding_gate.session["roles"] = ["admin"]
            from flask import render_template
            html = render_template("users.html")
        self.assertNotIn("<th>Password</th>", html)
        self.assertNotIn('{ title: "Password" }', html)
        self.assertNotIn("user.password", html)


if __name__ == "__main__":
    unittest.main()
