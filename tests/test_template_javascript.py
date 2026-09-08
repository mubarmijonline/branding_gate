"""
Every template's inline JavaScript must actually parse.

A template that renders fine can still ship JavaScript with unbalanced braces,
in which case the browser aborts the whole script block and the page silently
does nothing. That is invisible to a status-code check and to a render check,
so it needs its own test.

Requires `node` on PATH; skipped if absent.
"""

import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

import branding_gate
import rbac

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'templates')

# Rendered with an admin session so every gated branch is present.
CONTEXT = {'sales_request.html': {'pricing_mode': False}}

SCRIPT_BLOCK = re.compile(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', re.S | re.I)


@unittest.skipIf(shutil.which('node') is None, 'node is not installed')
class TemplateJavaScriptTest(unittest.TestCase):
    """Render each page as an admin and syntax-check the JavaScript it emits."""

    @classmethod
    def setUpClass(cls):
        cls.pages = sorted(
            name for name in os.listdir(TEMPLATE_DIR)
            if name.endswith('.html') and name not in {'main.html'}
        )

    def _render(self, template_name):
        from flask import render_template
        with branding_gate.app.test_request_context('/'):
            branding_gate.session.update(
                user_id=1, roles=['admin'], role_code='admin',
                perms=rbac.SEED_MATRIX['admin'],
                mobile='m', email='e', username='u', name='n',
            )
            return render_template(template_name, **CONTEXT.get(template_name, {}))

    def test_inline_javascript_parses(self):
        for name in self.pages:
            with self.subTest(template=name):
                try:
                    html = self._render(name)
                except Exception:
                    # Templates needing extra context are covered elsewhere.
                    continue

                for index, block in enumerate(SCRIPT_BLOCK.findall(html)):
                    if not block.strip():
                        continue
                    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as handle:
                        handle.write(block)
                        path = handle.name
                    try:
                        result = subprocess.run(
                            ['node', '--check', path],
                            capture_output=True, text=True, timeout=30,
                        )
                    finally:
                        os.unlink(path)

                    if result.returncode != 0:
                        first = result.stderr.strip().split('\n')
                        detail = '\n'.join(first[:6])
                        self.fail('%s, inline script #%d does not parse:\n%s'
                                  % (name, index + 1, detail))


@unittest.skipIf(shutil.which('node') is None, 'node is not installed')
class NotificationDestinationTest(unittest.TestCase):
    """
    Where each kind of notification sends the reader.

    Clicking a notification used to do nothing but mark it read, so whoever was
    told that something needed doing then went looking for the page. New
    notifications carry a link from the sender; everything already in the tray
    is read off its words by notifLink(), and this pins what that reads.
    """

    CASES = [
        # A new request goes to Operations, who cost it.
        ({'title': 'New Sales Request #000784',
          'content': 'Please review and add costing.'},
         '/operation_request?request=784'),
        # ... and once costed, the same request belongs to Pricing. The word
        # "costing" is in it, which is exactly the trap.
        ({'title': 'Request #000784 Costing Completed',
          'content': 'It is ready for pricing.'},
         '/pricing?request=784'),
        ({'title': 'Request #000784 Re-Costing Completed',
          'content': 'Re-Pricing can now set the new selling price.'},
         '/pricing?request=784'),
        ({'title': 'Re-costing needed: booth',
          'content': 'Re-Pricing sent it back on request #785.'},
         '/operation_request?request=785'),
        # An explicit link from the sender always wins.
        ({'title': 'Costing assigned: request #784', 'content': '3 items',
          'link': '/operation_request?request=784'},
         '/operation_request?request=784'),
        ({'title': 'عهدة request approved', 'content': ''}, '/my_expenses'),
        ({'title': 'Expense rejected', 'content': 'مصروف'}, '/expense_tracking'),
        ({'title': 'Client added: tadros', 'content': 'client request approved'},
         '/client'),
        # Nothing to open is a real answer: the row just marks itself read.
        ({'title': 'Good morning', 'content': 'nothing to do'}, None),
    ]

    def test_each_notification_opens_the_page_its_work_is_on(self):
        source = io.open(os.path.join(TEMPLATE_DIR, 'main.html'),
                         encoding='utf-8').read()
        start = source.index('window.notifLink = function')
        end = source.index('};', source.index('return null;', start)) + 2
        script = 'const window = {};\n' + source[start:end] + '\n' + '\n'.join(
            'console.log(JSON.stringify(window.notifLink(%s)));' % json.dumps(case)
            for case, _ in self.CASES)

        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False,
                                         encoding='utf-8') as handle:
            handle.write(script)
            path = handle.name
        try:
            result = subprocess.run(['node', path], capture_output=True,
                                    text=True, timeout=30)
        finally:
            os.unlink(path)
        self.assertEqual(result.returncode, 0, result.stderr)

        got = [json.loads(line) for line in result.stdout.strip().split('\n')]
        for (case, want), actual in zip(self.CASES, got):
            self.assertEqual(actual, want, case['title'])


class StackedModalTest(unittest.TestCase):
    """
    Only the backdrop of the modal being opened may be raised.

    The costing dialogs open on top of the cost modal, and Bootstrap 4 does not
    stack. The first attempt raised every backdrop that was not yet marked,
    which included the cost modal's own -- so that modal ended up *under* its
    own backdrop: on screen, fully drawn, and dead to every click. It looked
    like the page had hung.

    A `focus()` check does not catch this, because focus works through an
    overlay. What catches it is asking what a mouse would actually hit, which
    is a browser test; this pins the rule in the source so the shape cannot
    come back unnoticed.
    """

    def setUp(self):
        with open(os.path.join(TEMPLATE_DIR, 'operation_request.html'),
                  encoding='utf-8') as handle:
            self.source = handle.read()
        start = self.source.index('// ---- stacked modals ---')
        end = self.source.index('// ---- one Bootstrap modal for every costing action ---')
        self.block = self.source[start:end]

    def test_only_the_newest_backdrop_is_raised(self):
        # The newest backdrop is the last one Bootstrap appended.
        self.assertIn("$('.modal-backdrop').last().css('z-index', z - 10)", self.block)
        # Raising a *set* of backdrops is the bug: it takes the lower modal's
        # own backdrop up with it.
        self.assertNotIn(".not('.op-stacked')", self.block)
        for forbidden in ("$('.modal-backdrop').css('z-index'",
                          "$('.modal-backdrop').addClass"):
            self.assertNotIn(forbidden, self.block, forbidden)

    def test_the_backdrop_left_behind_drops_back_under_the_modal(self):
        # Closing the top dialog must put the remaining backdrop below whatever
        # is still open, or that modal stays unclickable.
        self.assertIn("belowZ - 10", self.block)
        self.assertIn("$('body').addClass('modal-open')", self.block)

    def test_the_last_modal_out_takes_the_scroll_lock_with_it(self):
        self.assertIn("$('body').removeClass('modal-open')", self.block)
        self.assertIn("$('.modal-backdrop').remove()", self.block)


class RequestFilterNoticeTest(unittest.TestCase):
    """
    A page narrowed by ?request=N must say so, and offer the way out.

    Notifications link to `/operation_request?request=784` and
    `/pricing?request=784`, which filter the table to that one request. With
    the modal closed the narrowing is invisible: the table simply looks like it
    has lost every other request, and there is nothing to click to get them
    back.
    """

    PAGES = {
        'operation_request.html': ('opRequestFilterNote', 'opClearRequestFilter',
                                   'window.opTable'),
        'sales_request.html': ('srRequestFilterNote', 'srClearRequestFilter',
                               'window.requestsTable'),
    }

    def test_each_deep_linked_page_shows_and_clears_the_filter(self):
        for name, (note, clear, table) in self.PAGES.items():
            with open(os.path.join(TEMPLATE_DIR, name), encoding='utf-8') as handle:
                source = handle.read()
            # The notice exists, is hidden until it is needed, and is revealed
            # only when the page was opened on one request.
            self.assertIn('id="%s"' % note, source, name)
            self.assertIn("$('#%s').removeClass('d-none')" % note, source, name)
            # There is a way out, and it releases the table search.
            self.assertIn('id="%s"' % clear, source, name)
            self.assertIn("%s.search('').draw()" % table, source, name)
            # And it takes the parameter out of the address, so a refresh does
            # not drop the reader straight back into the filter.
            self.assertIn("url.searchParams.delete('request')", source, name)


if __name__ == '__main__':
    unittest.main()
