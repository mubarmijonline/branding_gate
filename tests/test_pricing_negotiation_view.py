"""
What Pricing is told, and what Pricing can see.

Request 785 held one item the client had countered -- "coffee cup", 120
against the client's 110 -- and the Set Selling Prices window showed it as
"Priced" like the rest. The client's price, the reason and the two decisions
(re-price, or send it back for re-costing) were all inside a collapsed row, and
one badge said "NEGOTIATION" for three different states: waiting on the head,
waiting on re-costing, and waiting on Pricing. A glance at that window said
there was nothing to do.

And nobody at the desk heard about it. Pricing is held two ways -- the Pricing
roles, and a per-account flag that load_permissions() honours -- but the
audience was built from the roles alone. With every Pricing role account
inactive, "tell Pricing" reached one person.

The window's own logic is run here in node, on the states it has to tell apart.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

import MySQLdb
import MySQLdb.cursors

import branding_gate
import rbac

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _badge_logic():
    """The lines the page uses to decide an item's badge, verbatim."""
    with open(os.path.join(ROOT, 'templates', 'sales_request.html'), encoding='utf-8') as handle:
        page = handle.read()
    # Two blocks, not the span between them: everything in between belongs to
    # the card's markup and cannot run on its own.
    first = page.index('var activeNegotiation = item.active_negotiation || null;')
    first_end = page.index(');', page.index("item.negotiation_status === 'negotiated'", first)) + 2
    second = page.index('var needsPricing = !isNegotiation', first_end)
    second_end = page.index("Awaiting Cost</span>'));", second) + len("Awaiting Cost</span>'));")
    return page[first:first_end] + '\n' + page[second:second_end]


def _badge_for(item):
    if not shutil.which('node'):
        raise unittest.SkipTest('node is not installed')
    script = ('var item = %s;\n'
              'var sellPerItem = Number(item.sell_per_item || 0);\n'
              'var costPerItem = Number(item.cost_per_item || 0);\n' % json.dumps(item)
              + _badge_logic() +
              "\nconsole.log(JSON.stringify({badge: statusBadge.replace(/<[^>]+>/g, '').trim(),"
              " isNegotiation: isNegotiation}));")
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as handle:
        handle.write(script)
        path = handle.name
    try:
        result = subprocess.run(['node', path], capture_output=True, text=True, timeout=30)
    finally:
        os.unlink(path)
    if result.returncode != 0:
        raise AssertionError(result.stderr[:400])
    return json.loads(result.stdout)


def _item(negotiation_status, active_status):
    return {'id': 619, 'name': 'coffee cup', 'cost_per_item': 75.0, 'sell_per_item': 120.0,
            'approval_status': 'pending_negotiation', 'negotiation_status': negotiation_status,
            'active_negotiation': {'id': 640, 'status': active_status,
                                   'client_expected_price': 110.0, 'client_reason': 'overpriced',
                                   'destination_team': 'pricing',
                                   'new_cost_price': None, 'new_selling_price': None}}


class PricingWindowSaysWhoseMoveItIsTest(unittest.TestCase):

    def test_an_item_waiting_on_pricing_asks_for_a_decision(self):
        # Request 785's coffee cup, as it stands once the head has approved.
        verdict = _badge_for(_item('negotiated', 'pending_pricing'))
        self.assertTrue(verdict['isNegotiation'])
        self.assertIn('RE-PRICING REQUIRED', verdict['badge'])

    def test_a_priced_item_keeps_its_price_badge_under_negotiation(self):
        # The negotiation sits beside "Priced" rather than replacing it: the
        # item is priced, and that price is what is being argued about.
        verdict = _badge_for(_item('negotiated', 'pending_pricing'))
        self.assertIn('Priced', verdict['badge'])
        self.assertLess(verdict['badge'].index('Priced'),
                        verdict['badge'].index('RE-PRICING REQUIRED'))

    def test_an_item_still_with_the_head_says_so(self):
        verdict = _badge_for(_item('pending_negotiation', 'pending_sales_head'))
        self.assertIn('IN NEGOTIATION', verdict['badge'])

    def test_an_item_out_for_re_costing_says_so(self):
        verdict = _badge_for(_item('negotiated', 'pending_costing'))
        self.assertIn('AWAITING RE-COSTING', verdict['badge'])

    def test_an_ordinary_priced_item_is_unchanged(self):
        verdict = _badge_for({'id': 618, 'cost_per_item': 85.0, 'sell_per_item': 120.0,
                              'approval_status': 'approved', 'negotiation_status': 'none'})
        self.assertFalse(verdict['isNegotiation'])
        self.assertEqual(verdict['badge'], 'Priced')

    def test_an_item_awaiting_a_decision_opens_itself(self):
        with open(os.path.join(ROOT, 'templates', 'sales_request.html'), encoding='utf-8') as handle:
            page = handle.read()
        # The client's price, the reason and both buttons live in the body.
        self.assertIn("""<div class="collapse${negotiationNeedsAttention ? ' show' : ''}" id="${collapseId}">""", page)
        self.assertIn("""<div class="price-item-summary${negotiationNeedsAttention ? '' : ' collapsed'}\"""", page)
        # Waiting on the head is marked but not opened: it is not this desk's move.
        self.assertIn("var negotiationNeedsAttention = isPricingDecision || isAwaitingRecosting;", page)
        self.assertRegex(page, r'price-item-accordion--negotiation')


class EachItemSavesItselfTest(unittest.TestCase):
    """
    One item's action must not discard another item's work.

    Sending an item to re-costing closes and reloads the window. A price typed
    into another row and not yet saved went with it -- so re-costing one item
    silently threw away the re-pricing of the one above it.
    """

    def setUp(self):
        with open(os.path.join(ROOT, 'templates', 'sales_request.html'), encoding='utf-8') as handle:
            self.page = handle.read()

    def test_a_price_saves_when_the_field_is_left(self):
        self.assertIn("$(document).on('change', '.item-sell-price-input', function () {", self.page)
        self.assertIn('function savePriceForItem($input)', self.page)
        # One item at a time, through the endpoint that already exists.
        self.assertIn("data: JSON.stringify({ items: [{ item_id: itemId, sell_per_item: sellPerItem }] })",
                      self.page)

    def test_the_row_says_whether_it_saved(self):
        for state in ('Saving...', 'Saved', 'Not saved'):
            self.assertIn(state, self.page)

    def test_both_decisions_flush_what_is_typed_first(self):
        for handler in ('.pricing-send-to-costing', '.pricing-decline-negotiation'):
            start = self.page.index("$(document).on('click', '%s'" % handler)
            block = self.page[start:self.page.index("\n    });", start)]
            self.assertIn('window.flushPriceEdits().always(function () {', block, handler)
            self.assertLess(block.index('window.flushPriceEdits()'), block.index('$.ajax({'), handler)

    def test_a_saved_price_is_not_sent_twice(self):
        # The field's own value becomes the new baseline, so a second flush
        # before the reload does not repost it.
        save = self.page[self.page.index('function savePriceForItem($input)'):]
        save = save[:save.index('window.flushPriceEdits')]
        self.assertIn("$input.data('original-price', sellPerItem);", save)
        self.assertIn('Math.abs(sellPerItem - originalPrice) <= 0.001', save)


class _RollbackConnection:
    def __init__(self, raw): self.raw = raw
    def commit(self): pass
    def close(self): pass


class PricingDeskHearsAboutItTest(unittest.TestCase):

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self._cursor())

    def _undo(self):
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _make_user(self, username, is_pricing, is_active=1, manager=1):
        cur = self._cursor()
        cur.execute("SELECT id FROM rbac_role WHERE code = 'account_member'")
        role_id = cur.fetchone()['id']
        cur.execute("""INSERT INTO user (name, mobile, email, password, username, title,
                                         rbac_role_id, manager_id, is_active, is_pricing, date)
                       VALUES (%s, %s, %s, 'x', %s, 'Pricing desk test', %s, %s, %s, %s, NOW())""",
                    (username, '014%08d' % (abs(hash(username)) % 10 ** 8),
                     username + '@example.com', username, role_id, manager, is_active, is_pricing))
        user_id = cur.lastrowid
        cur.close()
        return user_id

    def test_an_account_flagged_for_pricing_is_part_of_the_desk(self):
        flagged = self._make_user('desk-flagged', is_pricing=1)
        self.assertIn(flagged, branding_gate.users_holding('sales_item.price'))

    def test_an_inactive_flagged_account_is_not(self):
        asleep = self._make_user('desk-asleep', is_pricing=1, is_active=0)
        self.assertNotIn(asleep, branding_gate.users_holding('sales_item.price'))

    def test_the_flag_does_not_widen_unrelated_audiences(self):
        flagged = self._make_user('desk-flagged-two', is_pricing=1)
        self.assertNotIn(flagged, branding_gate.users_holding('inventory.delete'))

    def test_the_desk_is_the_permissions_the_flag_grants(self):
        # Whatever load_permissions() gives a flagged account, the audience for
        # it includes them; the two cannot drift apart.
        flagged = self._make_user('desk-flagged-three', is_pricing=1)
        for permission in rbac.PRICING_FLAG_PERMISSIONS:
            with self.subTest(permission=permission):
                self.assertIn(flagged, branding_gate.users_holding(permission))


class ARefusalSaysWhoAndWhyTest(unittest.TestCase):
    """
    "Error in Saving price", and nothing anywhere to say why.

    Saving a price came back 403 for somebody, and the server kept no record
    of who was refused or for which permission: the access log has the
    refusal but not the account, and behind a shared proxy address one
    person's 403 looks exactly like another's. The page then threw the
    server's answer away and showed a generic failure.
    """

    def setUp(self):
        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_RollbackConnection(self.raw), self._cursor())
        branding_gate.app.config['TESTING'] = True

        cur = self._cursor()
        cur.execute("SELECT id FROM rbac_role WHERE code = 'account_team_leader'")
        role_id = cur.fetchone()['id']
        cur.execute("""INSERT INTO user (name, mobile, email, password, username, title,
                                         rbac_role_id, manager_id, is_active, is_pricing, date)
                       VALUES ('refused-probe', '0179000111', 'refused@example.com', 'x',
                               'refused-probe', 'Refusal test', %s, 1, 1, 0, NOW())""", (role_id,))
        self.user_id = cur.lastrowid
        cur.close()

    def _undo(self):
        branding_gate.connection = self.original
        self.raw.rollback()
        self.raw.close()

    def _cursor(self):
        return self.raw.cursor(MySQLdb.cursors.DictCursor)

    def _client(self):
        perms, role_code = branding_gate.load_permissions(self.user_id)
        self.assertIsNone(perms.get('sales_item.price'), 'this account must not price')
        client = branding_gate.app.test_client()
        with client.session_transaction() as flask_session:
            flask_session.update({'user_id': self.user_id, 'mobile': 'm', 'email': 'e',
                                  'username': 'u', 'name': 'Refused', 'roles': [role_code],
                                  'perms': perms, 'role_code': role_code})
        return client

    def test_the_answer_names_the_permission(self):
        response = self._client().post('/api/sales/requests/785/set-prices',
                                       json={'items': [{'item_id': 618, 'sell_per_item': 131}]})
        self.assertEqual(response.status_code, 403)
        body = response.get_json()
        self.assertIn('sales_item.price', body.get('permission', []))
        self.assertIn('permission', body['error'])
        self.assertNotEqual(body['error'], 'Forbidden')

    def test_the_log_names_the_account(self):
        import logging
        records = []

        class Catch(logging.Handler):
            def emit(self, record): records.append(record.getMessage())

        handler = Catch()
        branding_gate.app.logger.addHandler(handler)
        try:
            self._client().post('/api/sales/requests/785/set-prices',
                                json={'items': [{'item_id': 618, 'sell_per_item': 131}]})
        finally:
            branding_gate.app.logger.removeHandler(handler)
        refusals = [line for line in records if 'Refused' in line]
        self.assertTrue(refusals, 'the refusal was not logged')
        self.assertIn('sales_item.price', refusals[0])
        self.assertIn(str(self.user_id), refusals[0])

    def test_the_window_shows_what_the_server_said(self):
        with open(os.path.join(ROOT, 'templates', 'sales_request.html'), encoding='utf-8') as handle:
            page = handle.read()
        self.assertIn("Swal.fire('Error!', body.error || body.message ||", page)
        self.assertNotIn("Swal.fire('Error!', 'Error saving prices: ' + error, 'error');", page)


if __name__ == '__main__':
    unittest.main()
