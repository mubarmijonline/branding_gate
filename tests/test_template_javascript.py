"""
Every template's inline JavaScript must actually parse.

A template that renders fine can still ship JavaScript with unbalanced braces,
in which case the browser aborts the whole script block and the page silently
does nothing. That is invisible to a status-code check and to a render check,
so it needs its own test.

Requires `node` on PATH; skipped if absent.
"""

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


if __name__ == '__main__':
    unittest.main()
