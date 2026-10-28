"""
Design requests: the rules, with no Flask and no MySQL.

An Account Manager or Sales person asks the design team for work. The request
carries a shared header (company, client, event date, deadline) and one or
more items, each in a category with that category's fields. The head of the
design team assigns a designer, the designer delivers, the head approves or
sends it back, and the person who asked takes an approved request on to
Operations.

The same module serves 2D and 3D: `designer_kind` on the request says which
team it is for, and nothing else differs. Everything decidable without a
connection is decided here so it can be unit-tested the way costing.py is.
"""

from decimal import Decimal, InvalidOperation

DESIGNER_KINDS = ('2d', '3d')

# Status machine. A request is never deleted; "rejected" is a state it can
# leave again by being delivered anew, so the log keeps the whole story.
SUBMITTED = 'submitted'
ASSIGNED = 'assigned'
DELIVERED = 'delivered'
APPROVED = 'approved'
REJECTED = 'rejected'
SENT_TO_OPERATION = 'sent_to_operation'
STATES = (SUBMITTED, ASSIGNED, DELIVERED, APPROVED, REJECTED, SENT_TO_OPERATION)

STATE_LABELS = {
    SUBMITTED: 'Submitted',
    ASSIGNED: 'With designer',
    DELIVERED: 'Delivered, awaiting approval',
    APPROVED: 'Approved',
    REJECTED: 'Sent back',
    SENT_TO_OPERATION: 'Sent to Operation',
}

# What lands in design_request_log. A closed vocabulary so the trail can be
# filtered rather than grepped.
ACTIONS = (
    'submitted',
    'assigned',
    'reassigned',
    'delivered',
    'approved',
    'rejected',
    'sent_to_operation',
    'file_attached',
)

# The seven tabs, in the order the spec draws them.
CATEGORIES = (
    ('social_media', 'Social Media'),
    ('printing_production', 'Printing & Production'),
    ('video', 'Video'),
    ('mockup_reference', 'Mockup & Reference'),
    ('identity', 'Identity'),
    ('presentation', 'Presentation'),
    ('other', 'Other'),
)
CATEGORY_CODES = tuple(code for code, _label in CATEGORIES)
CATEGORY_LABELS = dict(CATEGORIES)

# Per-category fields beyond the four every item has (title, deadline,
# attachments, description). "Other" carries the union, as the spec draws it.
_PRINTING = ('size_h', 'size_w', 'size_l', 'quantity', 'printing_type')
_VIDEO = ('size_h', 'size_w', 'duration')
CATEGORY_FIELDS = {
    'social_media': (),
    'printing_production': _PRINTING,
    'video': _VIDEO,
    'mockup_reference': (),
    'identity': (),
    'presentation': (),
    'other': tuple(dict.fromkeys(_PRINTING + _VIDEO)),
}

# Offered as a list; the word is what is stored, so a type typed under
# "other" later is just another word (the supplier-type rule).
PRINTING_TYPES = ('Vinyl', 'Banner', 'Laser', 'Digital', 'Silkscreen', 'UV')

# Deliverables: a file of these types, or a link.
DELIVERABLE_EXTENSIONS = frozenset({'pdf', 'jpg', 'jpeg', 'png'})
# The brief that comes with an item may be anything a client sends.
BRIEF_EXTENSIONS = frozenset({'pdf', 'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp',
                              'ai', 'psd', 'svg', 'eps', 'zip', 'doc', 'docx',
                              'ppt', 'pptx', 'xls', 'xlsx', 'mp4', 'mov'})
MAX_FILE_BYTES = 25 * 1024 * 1024


class DesignRequestError(ValueError):
    """A refusal the caller should see, not a bug."""


def _number(value, field):
    if value in (None, ''):
        return None
    try:
        number = Decimal(str(value).replace(',', '').strip())
    except (InvalidOperation, ValueError):
        raise DesignRequestError('%s must be a number' % field)
    if number < 0:
        raise DesignRequestError('%s cannot be negative' % field)
    return number


def clean_item(raw):
    """
    One item as it will be stored, or a DesignRequestError saying what is
    wrong with it. Fields a category does not carry are dropped rather than
    stored blank, so a social-media item can never grow a quantity.
    """
    raw = raw or {}
    category = (raw.get('category') or '').strip().lower()
    if category not in CATEGORY_CODES:
        raise DesignRequestError('Pick a category for every item')
    title = (raw.get('title') or '').strip()
    if not title:
        raise DesignRequestError('Every item needs a request title')
    item = {
        'category': category,
        'title': title[:200],
        'deadline': (raw.get('deadline') or '').strip() or None,
        'description': (raw.get('description') or '').strip() or None,
        'size_h': None, 'size_w': None, 'size_l': None,
        'quantity': None, 'printing_type': None, 'duration': None,
    }
    fields = CATEGORY_FIELDS[category]
    for name in ('size_h', 'size_w', 'size_l'):
        if name in fields:
            item[name] = _number(raw.get(name), name.replace('_', ' '))
    if 'quantity' in fields:
        quantity = _number(raw.get('quantity'), 'quantity')
        if quantity is not None and quantity != quantity.to_integral_value():
            raise DesignRequestError('quantity must be a whole number of units')
        item['quantity'] = int(quantity) if quantity is not None else None
    if 'printing_type' in fields:
        item['printing_type'] = (raw.get('printing_type') or '').strip()[:60] or None
    if 'duration' in fields:
        item['duration'] = (raw.get('duration') or '').strip()[:60] or None
    return item


def clean_header(raw):
    """The shared header. A client or a company is enough to say who it is for."""
    raw = raw or {}
    kind = (raw.get('designer_kind') or '2d').strip().lower()
    if kind not in DESIGNER_KINDS:
        raise DesignRequestError('Designer kind must be 2d or 3d')

    def _id(name):
        value = raw.get(name)
        if value in (None, '', 0, '0'):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            raise DesignRequestError('%s is not a valid choice' % name)

    header = {
        'designer_kind': kind,
        'company_id': _id('company_id'),
        'client_id': _id('client_id'),
        'event_date': (raw.get('event_date') or '').strip() or None,
        'deadline': (raw.get('deadline') or '').strip() or None,
        'notes': (raw.get('notes') or '').strip() or None,
    }
    if not header['company_id'] and not header['client_id']:
        raise DesignRequestError('Say which company or client the design is for')
    return header


# ---------------------------------------------------------------------------
# Transitions. Each check answers "may this happen now?" and raises otherwise;
# the route does the writing.
# ---------------------------------------------------------------------------

def check_assign(status, assignee_kind, request_kind):
    """A designer from the right team, while the request is still open."""
    if status in (APPROVED, SENT_TO_OPERATION):
        raise DesignRequestError('This request has been approved; it cannot be reassigned.')
    if assignee_kind != request_kind:
        raise DesignRequestError('Pick a designer from the %s team.' % request_kind.upper())
    return 'reassigned' if status not in (SUBMITTED,) else 'assigned'


def check_deliver(status, actor_id, assignee_id):
    """Only the designer it is with, and only while it is with them."""
    if status not in (ASSIGNED, REJECTED):
        raise DesignRequestError('This request is not waiting on a delivery.')
    if actor_id != assignee_id:
        raise DesignRequestError('This request is assigned to somebody else.')
    return True


def check_decide(status, decision):
    """The head decides a delivery, and nothing else."""
    if decision not in ('approve', 'reject'):
        raise DesignRequestError('Decision must be approve or reject')
    if status != DELIVERED:
        raise DesignRequestError('Nothing has been delivered on this request yet.')
    return APPROVED if decision == 'approve' else REJECTED


def check_send_to_operation(status, actor_id, owner_id, unrestricted=False):
    """
    The person who asked takes an approved design to Operations. The admin
    may do it for them, which is what `unrestricted` means.
    """
    if status != APPROVED:
        raise DesignRequestError('Only an approved design can go to Operation.')
    if actor_id != owner_id and not unrestricted:
        raise DesignRequestError('Only the person who raised this request sends it to Operation.')
    return True


def deliverable_ok(filename=None, link=None):
    """A deliverable is a PDF, JPG or PNG, or a link to one. Returns the kind."""
    if link:
        link = link.strip()
        if not (link.startswith('http://') or link.startswith('https://')):
            raise DesignRequestError('A link must start with http:// or https://')
        return 'link'
    if filename and '.' in filename:
        extension = filename.rsplit('.', 1)[1].lower()
        if extension in DELIVERABLE_EXTENSIONS:
            return 'file'
    raise DesignRequestError('Upload a PDF, JPG or PNG, or paste a link.')


def portal_for(kind):
    """Where a request of this kind lives on the design side."""
    return '/design-3d' if kind == '3d' else '/design-2d'
