"""
Every place a notification can lead must be a page that exists.

An account manager and the account head tapped their notifications and landed
on "Not Found". Most notifications are stored without a link, so the tray in
main.html reads the words and picks a page -- and it picked `/my_expenses` and
`/expense_tracking`, pages the app serves as `/my-expenses` and
`/expense-tracking`. Nothing checked either path against the routes.

This reads every path the tray can return and every literal link the server
attaches, and asks the app whether it serves each one.
"""

import os
import re
import unittest

import branding_gate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _served_pages():
    return {rule.rule for rule in branding_gate.app.url_map.iter_rules()
            if 'GET' in rule.methods}


def _tray_paths():
    with open(os.path.join(ROOT, 'templates', 'main.html'), encoding='utf-8') as handle:
        page = handle.read()
    start = page.index('window.notifLink = function')
    body = page[start:page.index('\n};', start)]
    return sorted(set(re.findall(r"'(/[A-Za-z0-9_\-/]+)", body)))


def _server_links():
    with open(os.path.join(ROOT, 'branding_gate.py'), encoding='utf-8') as handle:
        source = handle.read()
    found = re.findall(r"""(?:\blink|deep_link)\s*=\s*f?['"](/[A-Za-z0-9_\-/]+)""", source)
    return sorted(set(found))


class NotificationLinksTest(unittest.TestCase):

    def test_every_page_the_tray_can_open_exists(self):
        served = _served_pages()
        paths = _tray_paths()
        self.assertTrue(paths, 'found no paths in notifLink -- the parser needs updating')
        missing = [path for path in paths if path not in served]
        self.assertEqual(missing, [], 'the tray sends people to pages that do not exist')

    def test_every_link_the_server_attaches_exists(self):
        served = _served_pages()
        links = _server_links()
        self.assertTrue(links, 'found no link= literals -- the parser needs updating')
        missing = [link for link in links if link not in served]
        self.assertEqual(missing, [], 'a notification links to a page that does not exist')

    def test_custody_goes_to_the_approver_or_the_requester(self):
        with open(os.path.join(ROOT, 'templates', 'main.html'), encoding='utf-8') as handle:
            page = handle.read()
        self.assertIn("'/expense-tracking-approval' : '/my-expenses'", page)
        self.assertNotIn("'/my_expenses'", page)
        self.assertNotIn("'/expense_tracking'", page)


if __name__ == '__main__':
    unittest.main()
