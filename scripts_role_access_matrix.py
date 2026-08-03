#!/usr/bin/env python
"""
Probe every GET route as every role and report what each one actually gets.

Distinguishes four outcomes, because an HTTP 200 is not proof a page worked:

  OK       200 and real content
  DENIED   403, or 200 whose body is the template's access-denied branch
  BROKEN   500, or a JSON body reporting failure
  REDIRECT 302 (recorded with its target)

Only GET routes are exercised, since POST/PUT/DELETE would mutate live data.
Write routes are reported separately from their declared permission.

    branding_gate_VENV/bin/python scripts_role_access_matrix.py            # summary
    branding_gate_VENV/bin/python scripts_role_access_matrix.py --detail sales_member
    branding_gate_VENV/bin/python scripts_role_access_matrix.py --json out.json
"""

import argparse
import json
import sys

import branding_gate as bg
import rbac

DENIAL_MARKERS = (
    'You do not have permission to view this page',
    'You do not have permission to access',
    'Access Denied!',
)

# Route parameters need a real value to exercise the handler at all.
SAMPLE_IDS = {}


def build_sample_ids():
    conn, cur = bg.connection()

    def one(sql):
        cur.execute(sql)
        row = cur.fetchone()
        return list(row.values())[0] if row else 1

    ids = {
        'request_id': one("SELECT id FROM sales_request ORDER BY id LIMIT 1"),
        'item_id': one("SELECT id FROM sales_request_items ORDER BY id LIMIT 1"),
        'client_id': one("SELECT id FROM client ORDER BY id LIMIT 1"),
        'company_id': one("SELECT id FROM company ORDER BY id LIMIT 1"),
        'supplier_id': one("SELECT id FROM supplier ORDER BY id LIMIT 1"),
        'entity_id': one("SELECT id FROM entities ORDER BY id LIMIT 1"),
        'negotiation_id': one("SELECT id FROM negotiation_requests ORDER BY id LIMIT 1"),
        'user_id': 1,
        'team_id': one("SELECT team_id FROM team ORDER BY team_id LIMIT 1"),
        'department_id': one("SELECT id FROM department ORDER BY id LIMIT 1"),
        'role_id': one("SELECT id FROM rbac_role ORDER BY id LIMIT 1"),
        'trans_id': one("SELECT id FROM finance_transactions ORDER BY id LIMIT 1"),
        'expense_id': one("SELECT id FROM user_expense_tracking ORDER BY id LIMIT 1"),
        'tracking_id': one("SELECT id FROM expense_tracking ORDER BY id LIMIT 1"),
        'method_id': one("SELECT id FROM payment_methods ORDER BY id LIMIT 1"),
        'cat_id': one("SELECT id FROM finance_categories ORDER BY id LIMIT 1"),
    }
    cur.close()
    conn.close()
    for key in ('approval_id', 'comment_id', 'file_id', 'attachment_id', 'document_id',
                'alert_id', 'credit_id', 'component_id', 'template_id', 'inventory_id'):
        ids.setdefault(key, 1)
    return ids


def concrete_path(rule):
    """Fill URL parameters with real ids; return None if we cannot."""
    path = rule.rule
    for argument in rule.arguments:
        value = SAMPLE_IDS.get(argument)
        if value is None:
            return None
        for converter in ('int:', 'string:', 'path:', 'float:', ''):
            token = '<%s%s>' % (converter, argument)
            if token in path:
                path = path.replace(token, str(value))
                break
    return None if '<' in path else path


def classify(response):
    if response.status_code in (301, 302, 303, 307, 308):
        return 'REDIRECT', response.headers.get('Location', '')
    if response.status_code == 403:
        return 'DENIED', '403'
    if response.status_code >= 500:
        return 'BROKEN', str(response.status_code)
    if response.status_code == 404:
        return 'MISSING', '404'
    if response.status_code != 200:
        return 'OTHER', str(response.status_code)

    content_type = response.headers.get('Content-Type', '')
    raw = response.get_data()

    # File downloads (PDF, Excel, images) are binary and succeed by arriving.
    if not content_type.startswith(('text/', 'application/json')):
        return ('OK', '%s, %d bytes' % (content_type.split(';')[0], len(raw))) if raw \
            else ('BROKEN', 'empty %s' % content_type)

    body = raw.decode('utf-8', errors='replace')

    if 'application/json' in content_type:
        try:
            payload = json.loads(body)
        except ValueError:
            return 'BROKEN', 'unparseable JSON'
        if isinstance(payload, dict) and payload.get('success') is False:
            error = str(payload.get('error', ''))[:60]
            # A permission refusal expressed in the body rather than the status.
            if 'Forbidden' in error or 'authoriz' in error.lower():
                return 'DENIED', error
            return 'BROKEN', error
        return 'OK', ''

    for marker in DENIAL_MARKERS:
        if marker in body:
            return 'DENIED', 'rendered access-denied branch'
    if len(body) < 400:
        return 'BROKEN', 'suspiciously short HTML (%d bytes)' % len(body)

    # A page whose body gate failed still ships the shared shell -- navbar,
    # scripts, styles -- so byte size proves nothing. What disappears is the
    # page's own content. Every real page renders at least one card, table or
    # heading of its own; a gated-out one renders none.
    if not any(marker in body for marker in
               ('card-body', '<table', '<h1 ', '<h2 ', '<form ')):
        return 'DENIED', 'gate rendered no page content'
    return 'OK', ''


def client_for(user_id):
    perms, role_code = bg.load_permissions(user_id)
    client = bg.app.test_client()
    with client.session_transaction() as flask_session:
        flask_session.update({
            'user_id': user_id, 'mobile': 'probe', 'email': 'probe@example.com',
            'username': 'probe', 'name': 'probe',
            'roles': [role_code] if role_code else [],
            'perms': perms, 'role_code': role_code,
        })
    return client, role_code, perms


# Probing these would end the session and invalidate every later request.
SESSION_DESTROYING = {'static', 'logout', 'login'}


def gather_routes():
    html_routes, api_routes, write_routes = [], [], []
    for rule in sorted(bg.app.url_map.iter_rules(), key=lambda r: r.rule):
        if rule.endpoint in SESSION_DESTROYING:
            continue
        methods = rule.methods - {'HEAD', 'OPTIONS'}
        perms = getattr(bg.app.view_functions[rule.endpoint], '_perms', ()) or ()
        if 'GET' not in methods:
            write_routes.append((rule.rule, sorted(methods), rule.endpoint, perms))
            continue
        path = concrete_path(rule)
        if not path:
            continue
        target = api_routes if rule.rule.startswith('/api/') else html_routes
        target.append((path, rule.rule, rule.endpoint, perms))
    return html_routes, api_routes, write_routes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--detail', help='role code to list route by route')
    parser.add_argument('--json', dest='json_out', help='write the full matrix as JSON')
    args = parser.parse_args()

    global SAMPLE_IDS
    SAMPLE_IDS = build_sample_ids()

    conn, cur = bg.connection()
    cur.execute("""
        SELECT u.id, u.name, r.code AS role_code, r.level
        FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id
        WHERE u.username = 'a.diab' OR u.username LIKE 'rolecheck.%%'
        ORDER BY r.level, r.code
    """)
    accounts = cur.fetchall()
    cur.close()
    conn.close()

    html_routes, api_routes, write_routes = gather_routes()
    print("probing %d HTML routes and %d API routes as %d roles "
          "(%d write routes reported statically)\n"
          % (len(html_routes), len(api_routes), len(accounts), len(write_routes)))

    matrix = {}
    for account in accounts:
        client, role_code, perms = client_for(account['id'])
        result = {'user_id': account['id'], 'level': account['level'],
                  'permissions': len(perms), 'html': {}, 'api': {}}
        for path, pattern, endpoint, route_perms in html_routes:
            verdict, note = classify(client.get(path))
            result['html'][pattern] = {'verdict': verdict, 'note': note,
                                       'perms': list(route_perms)}
        # The HTML sweep must not have logged us out.
        probe = client.get('/api/refresh-roles')
        if probe.status_code == 401:
            print("  !! session lost after HTML sweep for %s" % role_code)
        for path, pattern, endpoint, route_perms in api_routes:
            verdict, note = classify(client.get(path))
            result['api'][pattern] = {'verdict': verdict, 'note': note,
                                      'perms': list(route_perms)}
        matrix[role_code] = result

        def tally(section):
            counts = {}
            for entry in result[section].values():
                counts[entry['verdict']] = counts.get(entry['verdict'], 0) + 1
            return counts

        print("%-24s L%d  perms=%-3d  HTML %-46s API %s"
              % (role_code, account['level'], len(perms),
                 tally('html'), tally('api')))

    if args.json_out:
        with open(args.json_out, 'w') as handle:
            json.dump({'matrix': matrix,
                       'write_routes': [
                           {'rule': r, 'methods': m, 'endpoint': e, 'perms': list(p)}
                           for r, m, e, p in write_routes]},
                      handle, indent=2)
        print("\nfull matrix written to %s" % args.json_out)

    if args.detail:
        entry = matrix.get(args.detail)
        if not entry:
            print("\nunknown role: %s" % args.detail)
            return 1
        print("\n=== %s (user %d, %d permissions) ===" % (args.detail, entry['user_id'], entry['permissions']))
        for section in ('html', 'api'):
            print("\n-- %s --" % section.upper())
            for pattern, info in sorted(entry[section].items()):
                print("  %-8s %-58s %s" % (info['verdict'], pattern,
                                           info['note'] or ','.join(info['perms'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
