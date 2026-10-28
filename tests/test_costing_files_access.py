"""
Costing proposal files are supplier quotations, so cost: only the desks that
see cost open them, even with the direct link (Gamal, 2026-10-28). An Account
Manager who may see the request used to get the file. Rolled back like
test_costing.py.
"""

import os
import shutil
import tempfile
import unittest

import branding_gate
from test_costing import _CostingHarness


class CostingFilesAccessTest(_CostingHarness):

    def setUp(self):
        super().setUp()
        cur = self._cursor()
        for code in ('account_team_leader', 'pricing_specialist'):
            cur.execute("SELECT id FROM rbac_role WHERE code = %s", (code,))
            self.roles[code] = cur.fetchone()['id']
        cur.close()
        self.account = self._make_user('cf-account', 'account_team_leader', None)
        self.pricing = self._make_user('cf-pricing', 'pricing_specialist', None)
        self.tmp = tempfile.mkdtemp()
        self.original_uploads = branding_gate.UPLOADS_DIR
        branding_gate.UPLOADS_DIR = self.tmp
        os.makedirs(os.path.join(self.tmp, 'costing', '999999'))
        with open(os.path.join(self.tmp, 'costing', '999999', 'quote.jpg'), 'wb') as f:
            f.write(b'\xff\xd8quote')
        self.url = '/uploads/costing/999999/quote.jpg'

    def tearDown(self):
        branding_gate.UPLOADS_DIR = self.original_uploads
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def _get(self, user):
        r = self._client_for(user).get(self.url)
        r.close()
        return r.status_code

    def test_account_manager_is_refused_even_with_the_link(self):
        self.assertEqual(self._get(self.account), 403)

    def test_costing_and_pricing_desks_open_it(self):
        self.assertEqual(self._get(self.head), 200)
        self.assertEqual(self._get(self.member), 200)
        self.assertEqual(self._get(self.pricing), 200)


if __name__ == '__main__':
    unittest.main()
