"""
Design requests: the rules, with no Flask and no MySQL (Gamal, 2026-10-28).

Sales or Account Management asks Design for work. One request carries a header
(company, client, event date, deadline, 2D or 3D) and any number of items, each
of one category with that category's fields. Design assigns a designer, the
designer uploads the work and submits it, the Design Manager approves or sends
it back, and the requester sends the approved work to Operation.

Spec: docs/PRD.md, "Design Requests". Gamal's map defines the categories and
their fields; CATEGORIES below is that map.
"""

from datetime import date, datetime

DISCIPLINES = ('2d', '3d')

SUBMITTED = 'submitted'
ASSIGNED = 'assigned'
IN_REVIEW = 'in_review'
CHANGES = 'changes'
APPROVED = 'approved'
SENT = 'sent_to_operation'
CANCELLED = 'cancelled'
STATES = (SUBMITTED, ASSIGNED, IN_REVIEW, CHANGES, APPROVED, SENT, CANCELLED)

# action -> (states it may be taken from, state it leads to). Assign keeps a
# request that is already with a designer where it is: reassigning work that
# came back for changes must not lose the note.
TRANSITIONS = {
    'assign':  ((SUBMITTED, ASSIGNED, CHANGES), None),
    'submit':  ((ASSIGNED, CHANGES), IN_REVIEW),
    'approve': ((IN_REVIEW,), APPROVED),
    'changes': ((IN_REVIEW,), CHANGES),
    'send':    ((APPROVED,), SENT),
    'cancel':  ((SUBMITTED, ASSIGNED), CANCELLED),
}
# The designer uploads while the work is with them.
UPLOAD_STATES = (ASSIGNED, CHANGES)


class WorkflowError(ValueError):
    """An action the request's state does not allow."""


def transition(status, action):
    """The state `action` leads to from `status`, or WorkflowError."""
    if action not in TRANSITIONS:
        raise WorkflowError('Unknown action')
    sources, target = TRANSITIONS[action]
    if status not in sources:
        raise WorkflowError('This request is %s; that cannot be done now.' % status.replace('_', ' '))
    if action == 'assign':
        return ASSIGNED if status == SUBMITTED else status
    return target


# Every category keeps title, deadline, description and attachments; these are
# the extra fields each one keeps. "Other" has them all.
SIZE3 = ('size_h', 'size_w', 'size_l')
SIZE2 = ('size_h', 'size_w')
PRINTING = ('quantity', 'unit', 'printing_type')
CATEGORIES = {
    'social_media': ('Social Media', ()),
    'printing':     ('Printing & Production', SIZE3 + PRINTING),
    'video':        ('Video', SIZE2 + ('duration',)),
    'mockup':       ('Mockup & Reference', ()),
    'identity':     ('Identity', ()),
    'presentation': ('Presentation', ()),
    'other':        ('Other', SIZE3 + PRINTING + ('duration',)),
}
PRINTING_TYPES = ('Vinyl', 'Banner', 'Laser', 'Digital', 'Silkscreen', 'UV')
# The units of a sales request item, so a printed piece reads the same in both.
UNITS = ('pcs', 'set', 'box', 'm', 'm2', 'kg', 'liter', 'hours', 'days')
EXTRA_FIELDS = SIZE3 + PRINTING + ('duration',)


def parse_date(value):
    """A YYYY-MM-DD string (or date) as a date; None when blank."""
    if value in (None, ''):
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
    except ValueError:
        raise WorkflowError('Dates are YYYY-MM-DD')


def _number(value, label):
    if value in (None, ''):
        return None
    try:
        n = float(str(value).replace(',', ''))
    except ValueError:
        raise WorkflowError('%s must be a number' % label)
    if n < 0 or n > 1e7:
        raise WorkflowError('%s is out of range' % label)
    return n


def clean_item(raw, default_deadline=None):
    """
    One item as it is stored: its category's fields, nothing else. A field the
    category does not have is dropped rather than refused, so switching tabs in
    the form cannot leave a stray value behind.
    """
    raw = raw or {}
    category = raw.get('category')
    if category not in CATEGORIES:
        raise WorkflowError('Pick a category for every item')
    title = (raw.get('title') or '').strip()
    if not title:
        raise WorkflowError('Every item needs a request title')
    keeps = CATEGORIES[category][1]
    item = {
        'category': category,
        'title': title[:255],
        'deadline': parse_date(raw.get('deadline')) or default_deadline,
        'description': (raw.get('description') or '').strip()[:5000] or None,
    }
    for field in EXTRA_FIELDS:
        item[field] = None
    for field in ('size_h', 'size_w', 'size_l', 'quantity'):
        if field in keeps:
            item[field] = _number(raw.get(field), field.replace('_', ' ').title())
    if 'unit' in keeps:
        unit = raw.get('unit') or 'pcs'
        if unit not in UNITS:
            raise WorkflowError('Unknown unit')
        item['unit'] = unit
    if 'printing_type' in keeps and raw.get('printing_type'):
        if raw['printing_type'] not in PRINTING_TYPES:
            raise WorkflowError('Unknown type of printing')
        item['printing_type'] = raw['printing_type']
    if 'duration' in keeps:
        item['duration'] = (raw.get('duration') or '').strip()[:50] or None
    return item


def clean_header(raw):
    """The shared header of a request."""
    raw = raw or {}
    discipline = raw.get('discipline') or '2d'
    if discipline not in DISCIPLINES:
        raise WorkflowError('2D or 3D')
    try:
        client_id = int(raw.get('client_id'))
    except (TypeError, ValueError):
        raise WorkflowError('Pick the client')
    company_id = raw.get('company_id')
    try:
        company_id = int(company_id) if company_id not in (None, '') else None
    except (TypeError, ValueError):
        raise WorkflowError('Unknown company')
    return {
        'discipline': discipline,
        'client_id': client_id,
        'company_id': company_id,
        'event_date': parse_date(raw.get('event_date')),
        'deadline': parse_date(raw.get('deadline')),
    }


if __name__ == '__main__':
    assert transition(SUBMITTED, 'assign') == ASSIGNED
    assert transition(CHANGES, 'assign') == CHANGES
    assert transition(IN_REVIEW, 'changes') == CHANGES
    item = clean_item({'category': 'video', 'title': 'Teaser', 'size_h': '1080',
                       'quantity': '5', 'duration': '30 s'})
    assert item['size_h'] == 1080 and item['quantity'] is None and item['duration'] == '30 s'
    print('ok')
