"""
Draw the target cascade as a PDF.

Printing the page from the browser is not an option here for the same reason it
was not for the organisation chart: the connectors and the grid are at the mercy
of the print pipeline. This draws it.

The layout engine is org_chart_pdf's -- same boxes, same elbow connectors, same
fit-to-page scaling -- because the shape being drawn is the same reporting line.
Only what goes inside a box differs, plus a summary table so the numbers can be
read without measuring boxes.
"""

from io import BytesIO

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas as pdfcanvas

from org_chart_pdf import (
    BOX_W, GAP_X, GAP_Y, MARGIN,
    INK, MUTED, LINE, BORDER,
    FONT, FONT_BOLD,
    build_forest, _page_header, _walk,
)

# Taller than the org chart's box: a name, a role and three numbers.
BOX_H = 78.0

GOOD = HexColor('#1b6e4d')
WARN = HexColor('#8a6410')
BAD = HexColor('#c0392b')
TINT = HexColor('#eef1fa')
RULE = HexColor('#e3e6f0')


def _money(value):
    if value is None:
        return '-'
    return '{:,.0f}'.format(value)


def measure(node):
    """Width of the subtree: children side by side, or one box."""
    if not node.children:
        node.width = BOX_W
        return node.width
    total = sum(measure(child) for child in node.children)
    total += GAP_X * (len(node.children) - 1)
    node.width = max(BOX_W, total)
    return node.width


def _place(node, left, top):
    """org_chart_pdf.place with this module's taller box."""
    node.y = top
    if not node.children:
        node.x = left + BOX_W / 2.0
        return
    cursor = left
    for child in node.children:
        _place(child, cursor, top - BOX_H - GAP_Y)
        cursor += child.width + GAP_X
    node.x = (node.children[0].x + node.children[-1].x) / 2.0


def _connectors(c, node):
    if not node.children:
        return
    c.setStrokeColor(LINE)
    c.setLineWidth(0.8)
    c.setLineCap(1)
    parent_bottom = node.y - BOX_H
    bus_y = parent_bottom - GAP_Y / 2.0
    c.line(node.x, parent_bottom, node.x, bus_y)
    if len(node.children) > 1:
        c.line(node.children[0].x, bus_y, node.children[-1].x, bus_y)
    for child in node.children:
        c.line(child.x, bus_y, child.x, child.y)
        # The amount handed down rides on the connector: that is the flow.
        target = child.person.get('target')
        if target is not None:
            label = _money(target)
            c.setFont(FONT_BOLD, 6.6)
            width = c.stringWidth(label, FONT_BOLD, 6.6) + 6
            c.setFillColor(white)
            c.rect(child.x - width / 2.0, child.y + 2.4, width, 9.0, stroke=0, fill=1)
            c.setFillColor(MUTED)
            c.drawCentredString(child.x, child.y + 4.8, label)
        _connectors(c, child)


def _draw_box(c, node):
    person = node.person
    w, h = BOX_W, BOX_H
    x, y = node.x - w / 2.0, node.y - h

    progress = person.get('progress')
    accent = MUTED
    if progress is not None:
        accent = GOOD if progress >= 100 else (BAD if progress < 40 else WARN)

    c.setStrokeColor(BORDER)
    c.setLineWidth(0.7)
    c.setFillColor(white)
    c.roundRect(x, y, w, h, 4, stroke=1, fill=1)

    strip = 4.0
    c.setFillColor(accent if person.get('target') is not None else BORDER)
    c.roundRect(x, y + h - strip, w, strip, 1.5, stroke=0, fill=1)

    pad = 6.0
    name = (person.get('name') or '').strip() or 'Unnamed'
    role = (person.get('role_name') or '').strip()
    team = (person.get('team_name') or '').strip()

    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 8.2)
    c.drawCentredString(node.x, y + h - strip - 11,
                        simpleSplit(name, FONT_BOLD, 8.2, w - 2 * pad)[0])

    c.setFillColor(MUTED)
    c.setFont(FONT, 6.6)
    c.drawCentredString(node.x, y + h - strip - 20, (team or role)[:36])

    # Target, then what was handed down and what is still free.
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 11)
    c.drawCentredString(node.x, y + h - strip - 34, _money(person.get('target')))

    c.setFont(FONT, 6.4)
    c.setFillColor(MUTED)
    line_y = y + h - strip - 44
    if person.get('is_leader'):
        c.drawCentredString(node.x, line_y, 'down %s   free %s' % (
            _money(person.get('assigned')), _money(person.get('unassigned'))))
        line_y -= 8.4
    achieved = person.get('team_achieved')
    label = 'achieved %s' % _money(achieved)
    if progress is not None:
        label += '  ·  %d%%' % round(progress)
    c.setFillColor(accent)
    c.setFont(FONT_BOLD, 6.6)
    c.drawCentredString(node.x, line_y, label)

    # A bar along the foot, so a page of boxes can be read at a glance.
    if progress is not None:
        bar_w = w - 2 * pad
        c.setFillColor(RULE)
        c.rect(x + pad, y + 5, bar_w, 3.4, stroke=0, fill=1)
        c.setFillColor(accent)
        c.rect(x + pad, y + 5, bar_w * min(1.0, max(0.0, progress / 100.0)), 3.4,
               stroke=0, fill=1)

    if person.get('set_by'):
        c.setFillColor(MUTED)
        c.setFont(FONT, 5.6)
        c.drawCentredString(node.x, y + 12.5, 'set by %s%s' % (
            person['set_by'][:22],
            ' · ' + person['set_on'] if person.get('set_on') else ''))


def _render_flow(c, root, page_w, page_h, title, subtitle):
    measure(root)
    _place(root, 0, 0)

    xs, ys = [], []
    _walk(root, lambda n: (xs.append(n.x), ys.append(n.y)))
    min_x, max_x = min(xs) - BOX_W / 2.0, max(xs) + BOX_W / 2.0
    min_y, max_y = min(ys) - BOX_H, max(ys)

    content_w = max(max_x - min_x, 1.0)
    content_h = max(max_y - min_y, 1.0)
    avail_w = page_w - 2 * MARGIN
    avail_h = page_h - 2 * MARGIN - 40

    scale = min(avail_w / content_w, avail_h / content_h)
    scale = max(0.45, min(scale, 1.8))

    _page_header(c, page_w, page_h, title, subtitle)
    c.saveState()
    c.translate(MARGIN + (avail_w - content_w * scale) / 2.0,
                MARGIN + (avail_h - content_h * scale) / 2.0 - (min_y * scale))
    c.scale(scale, scale)
    c.translate(-min_x, 0)
    _connectors(c, root)
    _walk(root, lambda n: _draw_box(c, n))
    c.restoreState()

    if scale < 0.999:
        c.setFillColor(MUTED)
        c.setFont(FONT, 7.4)
        c.drawRightString(page_w - MARGIN, MARGIN - 12,
                          'scaled to %d%% to fit' % round(scale * 100))
    c.showPage()


# Widths add up to the printable width of A3 landscape, so the table fills the
# sheet instead of huddling in the top-left corner of it.
_COLUMNS = [
    ('Person',      240, 'left'),
    ('Team',        170, 'left'),
    ('Target',      120, 'right'),
    ('Handed down', 120, 'right'),
    ('Unassigned',  120, 'right'),
    ('Achieved',    120, 'right'),
    ('%',            64, 'right'),
    ('Set by',      168, 'left'),
]

HEAD_SIZE = 8.0
CELL_SIZE = 9.6


def _render_table(c, rows, page_w, page_h, title, subtitle):
    """The same numbers as a list, because a chart cannot be read column-wise."""
    row_h = 22.0
    top = page_h - MARGIN - 46
    x0 = MARGIN

    def header():
        c.setFillColor(MUTED)
        c.setFont(FONT_BOLD, HEAD_SIZE)
        x = x0
        for label, width, align in _COLUMNS:
            if align == 'right':
                c.drawRightString(x + width - 6, top + 7, label.upper())
            else:
                c.drawString(x, top + 7, label.upper())
            x += width
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.8)
        c.line(x0, top, x, top)
        return x

    _page_header(c, page_w, page_h, title, subtitle)
    right_edge = header()
    y = top - row_h

    for row in rows:
        if y < MARGIN + 20:
            c.showPage()
            _page_header(c, page_w, page_h, title, subtitle + '  (continued)')
            right_edge = header()
            y = top - row_h

        progress = row.get('progress')
        accent = INK
        if progress is not None:
            accent = GOOD if progress >= 100 else (BAD if progress < 40 else WARN)

        indent = 14.0 * (row.get('depth') or 0)
        values = [
            (row.get('name') or '', INK, FONT_BOLD),
            (row.get('team_name') or ('' if row.get('is_leader') else '—'), MUTED, FONT),
            (_money(row.get('target')), INK, FONT),
            (_money(row.get('assigned')) if row.get('is_leader') else '-', MUTED, FONT),
            (_money(row.get('unassigned')) if row.get('is_leader') else '-', MUTED, FONT),
            (_money(row.get('team_achieved')), accent, FONT),
            ('%d%%' % round(progress) if progress is not None else '-', accent, FONT),
            (('%s%s' % (row.get('set_by') or '',
                        ' · ' + row['set_on'] if row.get('set_on') else ''))[:44]
             or '—', MUTED, FONT),
        ]

        x = x0
        for (label, width, align), (text, colour, font) in zip(_COLUMNS, values):
            c.setFillColor(colour)
            c.setFont(font, CELL_SIZE)
            if align == 'right':
                c.drawRightString(x + width - 6, y + 6, str(text))
            else:
                pad = indent if label == 'Person' else 0.0
                c.drawString(x + pad, y + 6, str(text)[:52])
            x += width

        c.setStrokeColor(RULE)
        c.setLineWidth(0.4)
        c.line(x0, y, right_edge, y)
        y -= row_h

    c.showPage()


def build(pages, title='Sales targets', subtitle=''):
    """
    Return the cascade as PDF bytes: per period, the flow, then the table.

    `pages` is [(period label, rows)]. The rows are the ones the page itself
    renders -- already scoped, already in reporting order -- so an export can
    never contain more than the person asking for it may see. A year is four
    sections of one document rather than four documents stapled together, which
    is why nothing here needs a PDF-merging dependency.
    """
    page_w, page_h = landscape(A3)
    buffer = BytesIO()
    c = pdfcanvas.Canvas(buffer, pagesize=(page_w, page_h))
    c.setTitle(title)

    drew = False
    for label, rows in pages:
        heading = '%s — %s' % (title, label) if label else title
        if not rows:
            continue
        # build_forest reads manager_id; the API leaves it out for anyone whose
        # manager is out of scope, which is what makes them a local root.
        for root in build_forest(rows):
            _render_flow(c, root, page_w, page_h, heading, subtitle)
        _render_table(c, rows, page_w, page_h, heading, subtitle)
        drew = True

    if not drew:
        _page_header(c, page_w, page_h, title, 'No targets to show.')
        c.showPage()

    c.save()
    return buffer.getvalue()
