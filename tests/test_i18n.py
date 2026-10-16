"""
Arabic for the whole interface, English by default.

The server keeps the choice in a cookie and marks <html lang/dir>; the page
loads the dictionary (static/i18n/ar.js) and the translator
(static/js/bg-i18n.js) only in Arabic. These checks cover the switch, the
markup each language gets, the dictionary's shape, and the translator's
matching rules, run in node the way the browser runs them.
"""

import json
import os
import re
import shutil
import subprocess
import unittest

import branding_gate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_dictionary():
    with open(os.path.join(ROOT, 'static/i18n/ar.js'), encoding='utf-8') as fh:
        text = fh.read()
    return json.loads(text.split('window.BG_AR = ', 1)[1].rstrip().rstrip(';'))


class LanguageSwitchTest(unittest.TestCase):

    def setUp(self):
        branding_gate.app.config['TESTING'] = True
        self.client = branding_gate.app.test_client()

    def test_default_is_english_and_loads_nothing(self):
        page = self.client.get('/login').data.decode()
        self.assertIn('<html lang="en" dir="ltr"', page)
        self.assertNotIn('i18n/ar.js', page)
        self.assertIn('href="/lang/ar"', page)

    def test_switch_sets_cookie_and_returns_to_the_page(self):
        r = self.client.get('/lang/ar', headers={'Referer': 'http://localhost/login?x=1'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers['Location'].endswith('/login?x=1'))
        self.assertIn('bg_lang=ar', r.headers['Set-Cookie'])
        page = self.client.get('/login').data.decode()
        self.assertIn('<html lang="ar" dir="rtl" class="i18n-pending"', page)
        for asset in ('i18n/ar.js', 'js/bg-i18n.js', 'css/bg-rtl.css'):
            self.assertIn(asset, page)
        self.assertIn('href="/lang/en"', page)

    def test_switch_never_redirects_off_site_and_rejects_unknown_codes(self):
        r = self.client.get('/lang/ar', headers={'Referer': 'https://evil.example/phish'})
        self.assertTrue(r.headers['Location'].endswith('/home'))
        r = self.client.get('/lang/xx')
        self.assertIn('bg_lang=en', r.headers['Set-Cookie'])


class DictionaryTest(unittest.TestCase):

    def test_placeholders_survive_translation(self):
        bad = [k for k, v in load_dictionary().items()
               if sorted(re.findall(r'\{\d\}', k)) != sorted(re.findall(r'\{\d\}', v))]
        self.assertEqual(bad, [])

    def test_every_value_is_arabic_or_a_kept_name(self):
        kept = {'English', 'Switch to English', 'CEO'}
        bad = [k for k, v in load_dictionary().items()
               if not re.search(r'[؀-ۿ]', v) and v not in kept]
        self.assertEqual(bad, [])


@unittest.skipUnless(shutil.which('node'), 'node not installed')
class TranslatorTest(unittest.TestCase):

    CASES = {
        'Save': 'حفظ',
        'Booth': 'Booth',
        'approved': 'معتمد',                                  # case-folded short label
        'Client Payments | مدفوعات العملاء': 'Client Payments | مدفوعات العملاء',  # bilingual: as written
        'booth': 'booth',                                     # protected: also an item name
        'Client approved: Save': 'وافق العميل: Save',          # holes carry data, untranslated
        '4d ago': 'منذ 4 يوم',                                # hole glued to a word
        'Showing 1 to 10 of 57 entries': 'عرض 1 إلى 10 من أصل 57 سجل',
        '3 client(s) · 5 request(s) · pharmcy': '3 عميل · 5 طلب · pharmcy',   # segments, data kept
        'Pending Collection:': 'قيد التحصيل:',                 # trailing punctuation kept
        'EVA pharma': 'EVA pharma',                            # data is left alone
        'Added by George Osama · 1 day(s) ago': 'أضافه George Osama · منذ 1 يوم',   # segments before templates
    }

    def test_matching_rules(self):
        script = """
global.window = global;
global.document = {documentElement: {getAttribute: () => 'ar', classList: {remove() {}}},
                   readyState: 'complete', body: null, querySelector: () => null,
                   createTreeWalker() { return {nextNode: () => null}; }};
global.MutationObserver = class { observe() {} };
global.NodeFilter = {SHOW_ELEMENT: 1, SHOW_TEXT: 4, FILTER_REJECT: 2, FILTER_ACCEPT: 1};
global.BG_AR_DATA = ['Booth'];
const fs = require('fs');
eval(fs.readFileSync(process.argv[1] + '/static/i18n/ar.js', 'utf8'));
eval(fs.readFileSync(process.argv[1] + '/static/js/bg-i18n.js', 'utf8'));
const cases = JSON.parse(process.argv[2]);
const out = {};
for (const k of Object.keys(cases)) out[k] = bgT(k);
process.stdout.write(JSON.stringify(out));
"""
        r = subprocess.run(['node', '-e', script, ROOT, json.dumps(self.CASES)],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), self.CASES)


if __name__ == '__main__':
    unittest.main()


class ProtectedDataTest(unittest.TestCase):
    """Stored values that equal a dictionary word are sent so they stay untranslated."""

    def setUp(self):
        import MySQLdb
        import MySQLdb.cursors

        class _Rollback:
            def __init__(self, raw): self.raw = raw
            def commit(self): pass
            def close(self): pass

        self.raw = MySQLdb.connect(host="localhost", user="ps", passwd="Aa@123456",
                                   db="branding_gate", charset="utf8mb4", use_unicode=True)
        self.raw.autocommit(False)
        self.original = branding_gate.connection
        self.addCleanup(self._undo)
        branding_gate.connection = lambda: (_Rollback(self.raw), self.raw.cursor(MySQLdb.cursors.DictCursor))
        branding_gate._i18n_protected_cache.update(at=0.0, words=[])
        cur = self.raw.cursor()
        for name, code in (('Save', 'I18N_T1'), ('Zebra Secret 9k', 'I18N_T2')):
            cur.execute("INSERT INTO payment_methods (method_name, method_code, method_type) VALUES (%s, %s, 'cash')",
                        (name, code))

    def _undo(self):
        branding_gate.connection = self.original
        branding_gate._i18n_protected_cache.update(at=0.0, words=[])
        self.raw.rollback()
        self.raw.close()

    def test_only_the_overlap_is_sent(self):
        words = branding_gate.i18n_protected_words()
        self.assertIn('save', words)                  # data that is also a dictionary word
        self.assertNotIn('zebra secret 9k', words)    # other data never reaches the page

    def test_arabic_pages_carry_the_list(self):
        client = branding_gate.app.test_client()
        client.set_cookie('bg_lang', 'ar')
        page = client.get('/login').data.decode()
        self.assertIn('window.BG_AR_DATA = [', page)
        self.assertIn('"save"', page)
