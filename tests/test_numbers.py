"""
Numbers, read and typed.

`static/js/bg-numbers.js` decides two things that used to be decided four
different ways: how an amount reads in a table, and what a form actually posts
when somebody typed separators into it. The second one matters most -- a route
that calls float() on "1,250" raises, and a reader that calls parseFloat() on
it gets 1 -- so the stripping is pinned here.

Requires `node` on PATH; skipped if absent.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(ROOT, 'static', 'js', 'bg-numbers.js')

# Enough of a DOM for the file to load outside a browser.
STUB = """
var listeners = {};
var document = {
  addEventListener: function (name, fn) { listeners[name] = fn; },
  querySelectorAll: function () { return []; }
};
var window = {};
"""


def run(expressions):
    """Load the helper against a stub DOM and evaluate each expression."""
    with open(HELPER, encoding='utf-8') as handle:
        helper = handle.read()
    script = STUB + helper + '\n' + '\n'.join(
        'console.log(JSON.stringify(%s));' % e for e in expressions)
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False,
                                     encoding='utf-8') as handle:
        handle.write(script)
        path = handle.name
    try:
        result = subprocess.run(['node', path], capture_output=True, text=True,
                                timeout=30)
    finally:
        os.unlink(path)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return [json.loads(line) for line in result.stdout.strip().split('\n')]


@unittest.skipIf(shutil.which('node') is None, 'node is not installed')
class NumberDisplayTest(unittest.TestCase):
    """What a table cell says."""

    def test_amounts_are_grouped(self):
        cases = [
            ('window.bgNumber(292975)', '292,975'),
            ('window.bgNumber(292975.5, 2)', '292,975.50'),
            ('window.bgNumber(0)', '0'),
            ('window.bgNumber(999)', '999'),
            ('window.bgNumber(1000)', '1,000'),
            ('window.bgNumber(-4500)', '-4,500'),
            # A number that arrived as a string, separators and all.
            ('window.bgNumber("21,600")', '21,600'),
            # Nothing to show is a dash, not "NaN" and not "0".
            ('window.bgNumber(null)', '-'),
            ('window.bgNumber("")', '-'),
            ('window.bgMoney(292975)', 'EGP 292,975.00'),
            ('window.bgMoney(1250.5, "")', '1,250.50'),
            ('window.bgMoney(null)', '-'),
        ]
        got = run([expr for expr, _ in cases])
        for (expr, want), actual in zip(cases, got):
            self.assertEqual(actual, want, expr)


@unittest.skipIf(shutil.which('node') is None, 'node is not installed')
class NumberInputTest(unittest.TestCase):
    """What a form holds, and what it posts."""

    def test_digits_group_as_they_are_typed(self):
        cases = [
            ('window.bgGroupDigits("1250")', '1,250'),
            ('window.bgGroupDigits("1250.5")', '1,250.5'),
            ('window.bgGroupDigits("1,250")', '1,250'),
            ('window.bgGroupDigits("00123")', '123'),
            ('window.bgGroupDigits("")', ''),
            # Half-typed decimals must survive: "12." is on the way to "12.5".
            ('window.bgGroupDigits("12.")', '12.'),
            # Two decimal places is as far as money goes.
            ('window.bgGroupDigits("1.239")', '1.23'),
            ('window.bgGroupDigits("abc")', ''),
        ]
        got = run([expr for expr, _ in cases])
        for (expr, want), actual in zip(cases, got):
            self.assertEqual(actual, want, expr)

    def test_what_reaches_the_server_has_no_separators(self):
        # float("1,250") raises and parseFloat("1,250") is 1: everything that
        # reads one of these fields goes through this first.
        cases = [
            ('window.bgPlainNumber("1,250")', '1250'),
            ('window.bgPlainNumber("292,975.50")', '292975.50'),
            ('window.bgPlainNumber("  1,000  ")', '1000'),
            ('window.bgPlainNumber("800")', '800'),
            ('window.bgPlainNumber("")', ''),
            ('window.bgPlainNumber(null)', ''),
        ]
        got = run([expr for expr, _ in cases])
        for (expr, want), actual in zip(cases, got):
            self.assertEqual(actual, want, expr)

    def test_a_grouped_amount_survives_the_round_trip(self):
        # Typed, grouped, stripped, parsed: the number the user meant.
        got = run(['Number(window.bgPlainNumber(window.bgGroupDigits("292975.5")))'])
        self.assertEqual(got[0], 292975.5)


@unittest.skipIf(shutil.which('node') is None, 'node is not installed')
class AmountFieldsAreComma_SafeTest(unittest.TestCase):
    """
    Every field marked for grouping has readers that strip the separators.

    A field that groups while something still calls parseFloat() straight on it
    is a silently wrong total, which is worse than no grouping at all.
    """

    FIELDS = {
        'templates/operation_request.html': ['item-cost-per-unit', 'opPropAmount'],
        'templates/sales_request.html': ['item-sell-price'],
        'templates/my_expenses.html': ['expenseAmount'],
        'templates/expense_tracking.html': ['expense-amount'],
    }

    def test_no_grouped_field_is_read_raw(self):
        offenders = []
        for path, fields in self.FIELDS.items():
            with open(os.path.join(ROOT, path), encoding='utf-8') as handle:
                source = handle.read()
            for line in source.split('\n'):
                if 'parseFloat' not in line and '.val()' not in line:
                    continue
                if 'bgPlainNumber' in line or 'bg-amount' in line:
                    continue
                for field in fields:
                    # The declaration itself is not a reader.
                    if field in line and ('parseFloat' in line or '.val()' in line):
                        offenders.append('%s: %s' % (path, line.strip()[:110]))
        self.assertEqual(offenders, [], 'grouped fields read without stripping:\n' +
                         '\n'.join(offenders))


if __name__ == '__main__':
    unittest.main()


class ApiReadsAreNotCachedTest(unittest.TestCase):
    """
    A JSON read must never come out of the browser cache.

    Every list on the site is a GET that some page reloads after a write. With
    no cache headers the browser is free to answer that reload from its own
    cache, so a row deleted a moment ago comes back and the next reload shows
    it gone -- the page appearing to flicker between two versions of the truth,
    which is what deleting an inventory item looked like.
    """

    def setUp(self):
        import branding_gate
        self.branding_gate = branding_gate
        branding_gate.app.config['TESTING'] = True
        perms, role = branding_gate.load_permissions(1)
        self.client = branding_gate.app.test_client()
        with self.client.session_transaction() as flask_session:
            flask_session.update({'user_id': 1, 'mobile': 'm', 'email': 'e',
                                  'username': 'u', 'name': 'n', 'roles': [role],
                                  'perms': perms, 'role_code': role})

    def test_json_reads_say_no_store(self):
        for path in ('/api/entities', '/api/inventory/items?type=regular&status=all'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn('no-store', response.headers.get('Cache-Control', ''), path)

    def test_a_page_keeps_its_own_caching(self):
        # Only /api/ GETs are touched; pages and static files are left alone.
        response = self.client.get('/home')
        self.assertNotIn('no-store', response.headers.get('Cache-Control') or '')


class InventoryDeleteHonestyTest(unittest.TestCase):
    """
    "Deleted successfully" over an item that is still on the page.

    An item with movements behind it cannot be removed -- the transactions
    refer to it -- so the route retires it instead, marking it discontinued.
    It then reported "Item deleted successfully", and the items API ignored the
    status parameter the page was sending, so the retired row came straight
    back into the list. The user deleted something, was told it worked, and
    watched it stay.
    """

    def setUp(self):
        import branding_gate
        self.branding_gate = branding_gate
        branding_gate.app.config['TESTING'] = True
        perms, role = branding_gate.load_permissions(1)
        self.client = branding_gate.app.test_client()
        with self.client.session_transaction() as flask_session:
            flask_session.update({'user_id': 1, 'mobile': 'm', 'email': 'e',
                                  'username': 'u', 'name': 'n', 'roles': [role],
                                  'perms': perms, 'role_code': role})

    def _codes(self, status):
        response = self.client.get('/api/inventory/items?type=regular&status=%s' % status)
        self.assertEqual(response.status_code, 200, status)
        return {item['id'] for item in response.get_json().get('items', [])}

    def test_a_retired_item_is_off_the_shelf_but_still_findable(self):
        # "All" is every item you still have; a retired one is found by asking.
        live = self._codes('all')
        retired = self._codes('discontinued')
        self.assertFalse(live & retired,
                         'a discontinued item is showing under All Status')

    def test_the_route_says_which_of_the_two_things_it_did(self):
        source = open('branding_gate.py', encoding='utf-8').read()
        self.assertIn("outcome, message = 'discontinued'", source)
        self.assertIn("outcome, message = 'deleted'", source)
        # ...and the page tells them apart.
        page = open('templates/inventory_management.html', encoding='utf-8').read()
        self.assertIn("res.outcome === 'discontinued'", page)
        self.assertIn('Item retired', page)

    def test_a_retired_item_can_be_looked_for(self):
        page = open('templates/inventory_management.html', encoding='utf-8').read()
        self.assertIn('<option value="discontinued">Discontinued</option>', page)


class ConnectionsAreClosedTest(unittest.TestCase):
    """
    A handler that fails must not keep its database connection.

    228 routes had an error path that returned a 500 without closing, and a few
    hundred of those exhausts MySQL's 151 connections -- at which point every
    page hangs waiting for one that is never coming back. The connection is now
    closed with the request whatever the handler does.
    """

    def test_the_teardown_hook_is_registered(self):
        import branding_gate
        names = [f.__name__ for f in
                 branding_gate.app.teardown_request_funcs.get(None, [])]
        self.assertIn('close_open_connections', names)

    def test_requests_do_not_accumulate_connections(self):
        import MySQLdb
        import branding_gate
        branding_gate.app.config['TESTING'] = True
        perms, role = branding_gate.load_permissions(1)
        client = branding_gate.app.test_client()
        with client.session_transaction() as flask_session:
            flask_session.update({'user_id': 1, 'mobile': 'm', 'email': 'e',
                                  'username': 'u', 'name': 'n', 'roles': [role],
                                  'perms': perms, 'role_code': role})

        def threads():
            conn = MySQLdb.connect(host='localhost', user='ps', passwd='Aa@123456',
                                   db='branding_gate', charset='utf8mb4')
            cur = conn.cursor()
            cur.execute("SHOW STATUS LIKE 'Threads_connected'")
            count = int(cur.fetchone()[1])
            conn.close()
            return count

        before = threads()
        for _ in range(20):
            client.get('/api/entities')
        after = threads()
        self.assertLessEqual(after - before, 3,
                             'connections accumulated: %d -> %d' % (before, after))
