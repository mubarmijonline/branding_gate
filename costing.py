"""
Costing by assignment: the rules, with no Flask and no MySQL.

Nobody types a cost onto an item any more. The Operations Head assigns an item
to one or more team leaders, each leader assigns it on to one or more of their
own people, each of those may put up as many proposals as they like -- an
amount with documents and images -- and the leader who assigned them picks the
one that wins. That accepted amount is what becomes the item's cost.

Two rules do most of the work and both live here:

* **You may only assign to your own direct reports.** The same reporting line
  the rest of the system uses, so a transfer needs no fixup, and there is no
  second notion of who works for whom.
* **You may only decide on a proposal you asked for.** The leader who assigned
  the author picks the winner. The Operations Head can decide anywhere, because
  someone has to be able to unstick a leader who is on leave.

Everything else is a state machine small enough to read.
"""

from targets import to_amount  # money is parsed in exactly one place

# Assignment lifecycle. An assignment is withdrawn rather than deleted so the
# log keeps the fact that somebody was once asked.
ASSIGNMENT_OPEN = 'open'
ASSIGNMENT_WITHDRAWN = 'withdrawn'
ASSIGNMENT_CLOSED = 'closed'
ASSIGNMENT_STATES = (ASSIGNMENT_OPEN, ASSIGNMENT_WITHDRAWN, ASSIGNMENT_CLOSED)

# Proposal lifecycle.
PROPOSAL_SUBMITTED = 'submitted'
PROPOSAL_ACCEPTED = 'accepted'
PROPOSAL_REJECTED = 'rejected'
PROPOSAL_WITHDRAWN = 'withdrawn'
PROPOSAL_STATES = (PROPOSAL_SUBMITTED, PROPOSAL_ACCEPTED,
                   PROPOSAL_REJECTED, PROPOSAL_WITHDRAWN)

# What lands in costing_log. Kept as a closed vocabulary so the trail can be
# read and filtered rather than grepped.
ACTIONS = (
    'assigned',
    'assignment_withdrawn',
    'proposal_submitted',
    'proposal_updated',
    'proposal_withdrawn',
    'proposal_accepted',
    'proposal_rejected',
    'acceptance_reversed',
    'file_attached',
    'file_removed',
)


class CostingError(ValueError):
    """A refusal the caller should see, not a bug."""


def check_assignment(actor_id, assignee_id, direct_report_ids, unrestricted=False):
    """
    May `actor_id` put this item on `assignee_id`'s desk?

    Direct reports only. `unrestricted` is the Operations Head's override, which
    exists so an absent leader cannot stall an item.
    """
    if actor_id == assignee_id:
        raise CostingError('You cannot assign costing to yourself.')
    if unrestricted:
        return True
    if assignee_id not in set(direct_report_ids or ()):
        raise CostingError('You can only assign costing to your own team.')
    return True


def check_proposal(assignment_status, existing_state=None):
    """
    May a proposal be put up or changed right now?

    Costing is only open while the assignment is; and once a proposal has been
    decided it is a record, not a draft.
    """
    if assignment_status != ASSIGNMENT_OPEN:
        raise CostingError('This item is no longer assigned to you.')
    if existing_state is not None and existing_state != PROPOSAL_SUBMITTED:
        raise CostingError('A proposal that has been decided cannot be changed.')
    return True


def check_decision(proposal_state, actor_id, assigned_by_id, unrestricted=False):
    """May `actor_id` accept or reject this proposal?"""
    if proposal_state != PROPOSAL_SUBMITTED:
        raise CostingError('That proposal has already been decided.')
    if unrestricted or actor_id == assigned_by_id:
        return True
    raise CostingError('Only the person who asked for this costing can decide it.')


def parse_amount(value):
    """A proposed cost. Zero is allowed -- some items genuinely cost nothing."""
    amount = to_amount(value)          # raises ValueError on rubbish or negatives
    return amount


def visible_proposal_ids(rows, me, direct_report_ids, unrestricted=False):
    """
    Filter proposals to what one person may see before a decision is made.

    A coster sees their own. The leader who asked for it sees it. The Head sees
    everything. An accepted proposal is the item's cost and is public to anyone
    who may see the item at all, so it is never filtered out here.
    """
    reports = set(direct_report_ids or ())
    out = []
    for row in rows:
        if (unrestricted
                or row.get('status') == PROPOSAL_ACCEPTED
                or row.get('author_id') == me
                or row.get('assigned_by') == me
                or row.get('author_id') in reports):
            out.append(row)
    return out


def demo():
    """Self-check: the shape of the workflow, and each refusal."""
    # Assigning
    assert check_assignment(1, 2, [2, 3]) is True
    for bad, reports, head in ((1, [3], False), (1, [], False)):
        try:
            check_assignment(bad, 2, reports, unrestricted=head)
            raise AssertionError('assigned outside the team')
        except CostingError:
            pass
    try:
        check_assignment(1, 1, [1])
        raise AssertionError('assigned to self')
    except CostingError:
        pass
    # The Head reaches past their own reports.
    assert check_assignment(1, 9, [], unrestricted=True) is True

    # Proposing
    assert check_proposal(ASSIGNMENT_OPEN) is True
    assert check_proposal(ASSIGNMENT_OPEN, PROPOSAL_SUBMITTED) is True
    for status, state in ((ASSIGNMENT_WITHDRAWN, None),
                          (ASSIGNMENT_CLOSED, None),
                          (ASSIGNMENT_OPEN, PROPOSAL_ACCEPTED)):
        try:
            check_proposal(status, state)
            raise AssertionError('proposed when it should be closed')
        except CostingError:
            pass

    # Deciding
    assert check_decision(PROPOSAL_SUBMITTED, 5, 5) is True
    assert check_decision(PROPOSAL_SUBMITTED, 1, 5, unrestricted=True) is True
    for state, actor, asker in ((PROPOSAL_ACCEPTED, 5, 5), (PROPOSAL_SUBMITTED, 7, 5)):
        try:
            check_decision(state, actor, asker)
            raise AssertionError('decided what was not theirs to decide')
        except CostingError:
            pass

    # Seeing
    rows = [
        {'id': 1, 'author_id': 10, 'assigned_by': 5, 'status': PROPOSAL_SUBMITTED},
        {'id': 2, 'author_id': 11, 'assigned_by': 6, 'status': PROPOSAL_SUBMITTED},
        {'id': 3, 'author_id': 12, 'assigned_by': 6, 'status': PROPOSAL_ACCEPTED},
    ]
    assert [r['id'] for r in visible_proposal_ids(rows, 10, [])] == [1, 3]
    assert [r['id'] for r in visible_proposal_ids(rows, 5, [])] == [1, 3]
    assert [r['id'] for r in visible_proposal_ids(rows, 6, [11])] == [2, 3]
    assert [r['id'] for r in visible_proposal_ids(rows, 99, [], True)] == [1, 2, 3]

    assert str(parse_amount('1,250.50')) == '1250.50'
    try:
        parse_amount('-1')
        raise AssertionError('negative cost accepted')
    except ValueError:
        pass
    print('costing.py self-check passed')


if __name__ == '__main__':
    demo()
