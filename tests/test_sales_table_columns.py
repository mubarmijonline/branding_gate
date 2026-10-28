"""
Sales Requests table order (Gamal, 2026-10-28): Client Approval right before
Priority, in the header and in the DataTables columns, which are moved by name.
"""

import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = open(os.path.join(HERE, '..', 'templates', 'sales_request.html'), encoding='utf-8').read()


class SalesTableColumnsTest(unittest.TestCase):

    def test_header_has_client_approval_before_priority(self):
        thead = PAGE[PAGE.index('<table id="requests-table"') if '<table id="requests-table"' in PAGE else PAGE.index('requests-table'):]
        heads = re.findall(r'<th[^>]*>([^<{]+)</th>', thead[:thead.index('</thead>')])
        self.assertEqual(heads.index('Client Approval') + 1, heads.index('Priority'), heads)
        self.assertEqual(heads.count('Client Approval'), 1)

    def test_columns_are_moved_to_match(self):
        self.assertIn("c.data === 'client_approval_stage'", PAGE)
        self.assertIn("c.name === 'priority'", PAGE)


if __name__ == '__main__':
    unittest.main()
