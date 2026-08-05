"""
Sales targets: the arithmetic and the tree, with no Flask and no MySQL.

A target is one number for one person for one quarter. It is set by that
person's manager, and the manager may never hand out more than they were
given: the sum of a manager's direct reports' targets is capped by the
manager's own target. The split does not have to be even -- 200,000 and
800,000 out of 1,000,000 is exactly the intended shape -- and any remainder
may be left unassigned.

Nobody at the top has a target, so the first assignment (CEO -> Sales Head)
is uncapped. Everything below it is bounded by construction.

Keeping this module free of the database mirrors rbac.py: the rules are a
readable diff and are tested without a server.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

# Quarter number -> (first month, last month)
_QUARTER_MONTHS = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}

_LAST_DAY = {1: 31, 3: 31, 5: 31, 7: 31, 8: 31, 10: 31, 12: 31,
             4: 30, 6: 30, 9: 30, 11: 30}

ZERO = Decimal('0')


class InvalidPeriod(ValueError):
    """The period string is not a quarter this system recognises."""


def parse_period(period):
    """'2026-Q3' -> (2026, 3). Raises InvalidPeriod on anything else."""
    text = (period or '').strip().upper()
    year, _, quarter = text.partition('-Q')
    if not quarter or not year.isdigit() or not quarter.isdigit():
        raise InvalidPeriod('Period must look like 2026-Q3, got %r' % period)
    year, quarter = int(year), int(quarter)
    if year < 2000 or year > 2999 or quarter not in _QUARTER_MONTHS:
        raise InvalidPeriod('Period must look like 2026-Q3, got %r' % period)
    return year, quarter


def period_bounds(period):
    """Return the inclusive (first day, last day) of the quarter."""
    year, quarter = parse_period(period)
    first_month, last_month = _QUARTER_MONTHS[quarter]
    return date(year, first_month, 1), date(year, last_month, _LAST_DAY[last_month])


def current_period(today=None):
    """The quarter a date falls in, as a period string."""
    today = today or date.today()
    return '%d-Q%d' % (today.year, (today.month - 1) // 3 + 1)


def period_choices(today=None, back=4, forward=2):
    """A window of quarters around today, oldest first, for a period picker."""
    year, quarter = parse_period(current_period(today))
    index = year * 4 + (quarter - 1)
    out = []
    for offset in range(-back, forward + 1):
        n = index + offset
        out.append('%d-Q%d' % (n // 4, n % 4 + 1))
    return out


def to_amount(value):
    """
    Coerce user input to a non-negative money amount.

    Raises ValueError rather than guessing, so a typo never becomes a target.
    """
    try:
        amount = Decimal(str(value).strip().replace(',', ''))
    except (InvalidOperation, AttributeError, TypeError):
        raise ValueError('Amount must be a number')
    if amount.is_nan() or amount.is_infinite():
        raise ValueError('Amount must be a number')
    if amount < 0:
        raise ValueError('Amount cannot be negative')
    return amount.quantize(Decimal('0.01'))


def validate_assignment(amount, parent_amount, siblings_total, child_committed=ZERO):
    """
    Check one assignment against the two invariants. Returns an error message,
    or None when the assignment is allowed.

    `parent_amount`   the assigning manager's own target, or None when they
                      have none (the top of the tree, which is uncapped).
    `siblings_total`  the total already assigned to this person's *other*
                      siblings for the same period.
    `child_committed` the total this person has themselves already handed down.
    """
    if parent_amount is not None:
        remaining = parent_amount - siblings_total
        if amount > remaining:
            return (
                'That would hand out %s of a %s target. %s is left to assign.'
                % (_money(siblings_total + amount), _money(parent_amount), _money(remaining))
            )
    if amount < child_committed:
        return (
            'They have already distributed %s to their own team. Lower that first.'
            % _money(child_committed)
        )
    return None


def _money(amount):
    return '{:,.2f}'.format(amount or ZERO)


def build_tree(users, targets, achieved, visible_ids=None):
    """
    Flatten the reporting line into display rows, deepest branch expanded in
    place, each row carrying its own numbers and its subtree's.

    users        [{'id', 'name', 'manager_id', 'role_name', 'team_name'}, ...]
    targets      {user_id: Decimal}
    achieved     {user_id: Decimal}   own approved sell value for the period
    visible_ids  ids the caller may see, or None for everyone in `users`

    Rows come back in reporting order with a `depth`, so the page can indent
    without recursing in the template.
    """
    if visible_ids is not None:
        allowed = set(visible_ids)
        users = [u for u in users if u['id'] in allowed]

    by_id = {u['id']: u for u in users}
    children = {}
    for user in users:
        parent = user.get('manager_id')
        # A manager outside the visible set makes this person a local root.
        children.setdefault(parent if parent in by_id else None, []).append(user)
    for group in children.values():
        group.sort(key=lambda u: (u.get('name') or '').lower())

    rows = []

    def walk(user, depth):
        kids = children.get(user['id'], [])
        row = {
            'id': user['id'],
            'name': user.get('name'),
            'role_name': user.get('role_name'),
            'team_name': user.get('team_name'),
            'manager_id': user.get('manager_id'),
            'depth': depth,
            'is_leader': bool(kids),
            'target': targets.get(user['id']),
            'assigned': sum((targets.get(k['id']) or ZERO for k in kids), ZERO),
            'own_achieved': achieved.get(user['id']) or ZERO,
        }
        rows.append(row)
        subtree = row['own_achieved']
        for kid in kids:
            subtree += walk(kid, depth + 1)
        row['team_achieved'] = subtree
        target = row['target']
        row['unassigned'] = None if target is None else target - row['assigned']
        row['progress'] = (
            float(subtree / target * 100) if target and target > 0 else None
        )
        return subtree

    for root in children.get(None, []):
        walk(root, 0)
    return rows


def demo():
    """Self-check: the cascade in the brief, plus both refusals."""
    assert period_bounds('2026-Q3') == (date(2026, 7, 1), date(2026, 9, 30))
    assert current_period(date(2026, 8, 5)) == '2026-Q3'
    assert period_choices(date(2026, 1, 4), back=1, forward=1) == ['2025-Q4', '2026-Q1', '2026-Q2']

    million, small, big = Decimal('1000000'), Decimal('200000'), Decimal('800000')

    # The CEO has no target, so the first hand-down is uncapped.
    assert validate_assignment(million, None, ZERO) is None
    # An uneven split that fits is fine, in either order.
    assert validate_assignment(small, million, ZERO) is None
    assert validate_assignment(big, million, small) is None
    # One pound over the parent is not.
    assert validate_assignment(big + 1, million, small) is not None
    # Leaving a remainder unassigned is allowed.
    assert validate_assignment(Decimal('700000'), million, small) is None
    # A manager cannot be cut below what they already handed down.
    assert validate_assignment(small, million, ZERO, child_committed=big) is not None

    assert to_amount('1,000,000') == Decimal('1000000.00')
    try:
        to_amount('-5')
        raise AssertionError('negative target accepted')
    except ValueError:
        pass

    users = [
        {'id': 1, 'name': 'CEO', 'manager_id': None},
        {'id': 2, 'name': 'Head', 'manager_id': 1},
        {'id': 3, 'name': 'Leader A', 'manager_id': 2},
        {'id': 4, 'name': 'Member', 'manager_id': 3},
    ]
    targets = {2: million, 3: small, 4: Decimal('50000')}
    achieved = {4: Decimal('10000'), 3: Decimal('5000')}
    rows = build_tree(users, targets, achieved)
    assert [r['id'] for r in rows] == [1, 2, 3, 4]
    assert [r['depth'] for r in rows] == [0, 1, 2, 3]
    head = rows[1]
    assert head['assigned'] == small and head['unassigned'] == million - small
    assert head['team_achieved'] == Decimal('15000')

    # A team leader sees a tree rooted at themselves, not at the CEO.
    leader_view = build_tree(users, targets, achieved, visible_ids=[3, 4])
    assert [r['id'] for r in leader_view] == [3, 4]
    assert leader_view[0]['depth'] == 0
    print('targets.py self-check passed')


if __name__ == '__main__':
    demo()
