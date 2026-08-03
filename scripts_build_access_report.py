#!/usr/bin/env python
"""
Render the role-access report from a matrix produced by
scripts_role_access_matrix.py --json.

    branding_gate_VENV/bin/python scripts_role_access_matrix.py --json matrix.json
    branding_gate_VENV/bin/python scripts_build_access_report.py matrix.json report.html

The prose and styling live in docs/access_report_template.html; this fills in
the header row, the page-access grid and the per-role cards.
"""

import html
import json
import os
import sys

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'docs', 'access_report_template.html')

LEVEL = {0: 'Executive', 1: 'Head / Manager', 2: 'Team Leader', 3: 'Member'}

LABEL = {
    'admin': 'Admin / CEO', 'assistant': 'Assistant',
    'sales_head': 'Sales Head', 'sales_team_leader': 'Sales Team Leader',
    'sales_member': 'Sales Member',
    'marketing_manager': 'Marketing Manager', 'marketing_member': 'Marketing Member',
    'finance_manager': 'Finance Manager', 'finance_member': 'Finance Member',
    'account_director': 'Account Director', 'account_team_leader': 'Account Team Leader',
    'account_member': 'Account Member',
    'design_2d_head': '2D Designer Head', 'design_2d_member': '2D Designer',
    'design_3d_head': '3D Head', 'design_3d_member': '3D Designer',
    'operations_manager': 'Operations Manager',
    'operations_team_leader': 'Operations Team Leader',
    'operations_member': 'Operations Member',
    'pricing_manager': 'Pricing Manager', 'pricing_specialist': 'Pricing Specialist',
}

DEPT = {
    'admin': 'Executive', 'assistant': 'Executive',
    'sales_head': 'Sales', 'sales_team_leader': 'Sales', 'sales_member': 'Sales',
    'marketing_manager': 'Marketing', 'marketing_member': 'Marketing',
    'finance_manager': 'Finance', 'finance_member': 'Finance',
    'account_director': 'Account', 'account_team_leader': 'Account',
    'account_member': 'Account',
    'design_2d_head': '2D Design', 'design_2d_member': '2D Design',
    'design_3d_head': '3D Design', 'design_3d_member': '3D Design',
    'operations_manager': 'Operations', 'operations_team_leader': 'Operations',
    'operations_member': 'Operations',
    'pricing_manager': 'Pricing', 'pricing_specialist': 'Pricing',
}

# Endpoints that are not pages a person visits.
SKIP = {'/firebase-messaging-sw.js', '/get_notifications', '/main',
        '/uploads/items/<int:item_id>/<filename>'}

GLYPH = {'y': '●', 'n': '·', 'r': '→', 'b': '!'}
CLASS = {'OK': 'y', 'DENIED': 'n', 'REDIRECT': 'r', 'BROKEN': 'b',
         'MISSING': 'n', 'OTHER': 'r'}


def tidy(path):
    return path.replace('/sales_request_details/<int:request_id>',
                        '/sales_request_details/:id')


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    matrix_path, out_path = sys.argv[1], sys.argv[2]

    data = json.load(open(matrix_path, encoding='utf-8'))
    matrix, writes = data['matrix'], data['write_routes']

    pages = sorted({p for r in matrix for p in matrix[r]['html']} - SKIP)
    roles = sorted(matrix, key=lambda r: (matrix[r]['level'], r))

    head = ''.join('<th scope="col"><span>%s</span></th>' % html.escape(LABEL[r])
                   for r in roles)

    rows = []
    for page in pages:
        cells = ''
        for role in roles:
            klass = CLASS.get(matrix[role]['html'].get(page, {}).get('verdict', 'DENIED'), 'n')
            cells += '<td class="c c-%s">%s</td>' % (klass, GLYPH[klass])
        rows.append('<tr><th scope="row"><code>%s</code></th>%s</tr>'
                    % (html.escape(tidy(page)), cells))

    cards = []
    for role in roles:
        info = matrix[role]
        open_pages = [tidy(p) for p in pages
                      if info['html'].get(p, {}).get('verdict') == 'OK']
        api = info['api']
        api_ok = sum(1 for e in api.values() if e['verdict'] == 'OK')
        api_gated = api_ok + sum(1 for e in api.values() if e['verdict'] == 'DENIED')
        cards.append(
            '<article class="card">\n'
            '  <header><h3>%s</h3><p class="meta"><span class="lvl">%s</span> · %s · '
            '<code>%s</code></p></header>\n'
            '  <dl class="stats">\n'
            '    <div><dt>Permissions</dt><dd>%d</dd></div>\n'
            '    <div><dt>Pages</dt><dd>%d <span class="of">of %d</span></dd></div>\n'
            '    <div><dt>Read APIs</dt><dd>%d <span class="of">of %d</span></dd></div>\n'
            '  </dl>\n'
            '  <p class="pages">%s</p>\n'
            '</article>' % (
                html.escape(LABEL[role]), html.escape(LEVEL[info['level']]),
                html.escape(DEPT[role]), html.escape(role), info['permissions'],
                len(open_pages), len(pages), api_ok, api_gated,
                ' '.join('<code>%s</code>' % html.escape(p) for p in open_pages)))

    probes = len(roles) * (len(matrix['admin']['html']) + len(matrix['admin']['api']))
    page = open(TEMPLATE, encoding='utf-8').read()
    for token, value in (
        ('__HEAD__', head),
        ('__ROWS__', '\n'.join(rows)),
        ('__CARDS__', '\n'.join(cards)),
        ('__NROLES__', str(len(roles))),
        ('__NPAGES__', str(len(pages))),
        ('__NAPI__', str(len(matrix['admin']['api']))),
        ('__NWRITE__', str(len(writes))),
        ('__NPROBES__', '{:,}'.format(probes)),
    ):
        page = page.replace(token, value)

    open(out_path, 'w', encoding='utf-8').write(page)
    print("wrote %s: %d roles, %d pages, %d probes, %d bytes"
          % (out_path, len(roles), len(pages), probes, len(page)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
