"""
Draw the organisation chart as a PDF.

A CSS org chart printed through the browser either shrinks to nothing or loses
its connectors, because the layout is flex boxes and hairline borders that the
print pipeline is free to reinterpret. This draws the chart directly instead:
positions are computed here, lines are vector strokes, and the result is the
same in every viewer.

Layout is the classic tidy-tree walk. Each subtree is measured bottom-up, then
placed centred over its children. A branch that is still wider than the page is
scaled down, and only that branch.
"""

import os

from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas

# Box geometry, in points.
BOX_W = 150.0
BOX_H = 50.0
GAP_X = 12.0        # between siblings
GAP_Y = 44.0        # between a parent row and its children
MARGIN = 34.0

INK = HexColor('#2e3650')
MUTED = HexColor('#7b8397')
LINE = HexColor('#9aa2b5')
BORDER = HexColor('#c9cfdd')
TINT = HexColor('#eef1fa')

LEVEL_FILL = {
    0: HexColor('#2e3650'),
    1: HexColor('#dbe2fb'),
    2: HexColor('#e9ecf4'),
    3: white,
}
LEVEL_TEXT = {0: white, 1: HexColor('#2a3a86'), 2: INK, 3: INK}

FONT = 'Helvetica'
FONT_BOLD = 'Helvetica-Bold'


def _register_fonts():
    """Prefer DejaVu, which covers far more of Unicode than the built-ins."""
    global FONT, FONT_BOLD
    base = '/usr/share/fonts/truetype/dejavu'
    regular, bold = os.path.join(base, 'DejaVuSans.ttf'), os.path.join(base, 'DejaVuSans-Bold.ttf')
    if os.path.exists(regular) and os.path.exists(bold):
        try:
            pdfmetrics.registerFont(TTFont('OrgSans', regular))
            pdfmetrics.registerFont(TTFont('OrgSans-Bold', bold))
            FONT, FONT_BOLD = 'OrgSans', 'OrgSans-Bold'
        except Exception:
            pass


_register_fonts()


class Node(object):
    __slots__ = ('person', 'children', 'width', 'x', 'y')

    def __init__(self, person):
        self.person = person
        self.children = []
        self.width = BOX_W
        self.x = 0.0
        self.y = 0.0


def build_forest(people):
    """Turn flat rows into trees. Anyone whose manager is missing becomes a root."""
    nodes = {p['id']: Node(p) for p in people}
    roots = []
    for person in people:
        node = nodes[person['id']]
        parent = nodes.get(person.get('manager_id'))
        if parent is not None and parent is not node:
            parent.children.append(node)
        else:
            roots.append(node)
    for node in nodes.values():
        node.children.sort(key=lambda n: (n.person.get('role_level') or 3,
                                          n.person.get('name') or ''))
    return roots


def measure(node):
    """Width of the subtree: its children side by side, or one box."""
    if not node.children:
        node.width = BOX_W
        return node.width
    total = sum(measure(child) for child in node.children)
    total += GAP_X * (len(node.children) - 1)
    node.width = max(BOX_W, total)
    return node.width


def place(node, left, top):
    """Assign centres, parent above and centred over the span of its children."""
    node.y = top
    if not node.children:
        node.x = left + BOX_W / 2.0
        return
    cursor = left
    for child in node.children:
        place(child, cursor, top - BOX_H - GAP_Y)
        cursor += child.width + GAP_X
    node.x = (node.children[0].x + node.children[-1].x) / 2.0


def depth(node):
    return 1 + max([depth(c) for c in node.children] or [0])


def _draw_box(c, node, scale):
    person = node.person
    level = person.get('role_level')
    level = 3 if level is None else int(level)
    w, h = BOX_W, BOX_H
    x, y = node.x - w / 2.0, node.y - h

    c.setStrokeColor(BORDER)
    c.setLineWidth(0.7)
    c.setFillColor(white)
    c.roundRect(x, y, w, h, 4, stroke=1, fill=1)

    # A tinted strip carries the level, so rank is visible without reading.
    strip = 4.0
    c.setFillColor(LEVEL_FILL.get(level, white))
    c.roundRect(x, y + h - strip, w, strip, 1.5, stroke=0, fill=1)

    pad = 6.0
    name = (person.get('name') or '').strip() or 'Unnamed'
    role = (person.get('role_name') or 'No role').strip()
    dept = (person.get('rbac_department_name') or '').strip()

    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 8.2)
    for i, line in enumerate(simpleSplit(name, FONT_BOLD, 8.2, w - 2 * pad)[:2]):
        c.drawCentredString(node.x, y + h - strip - 11 - i * 9.4, line)

    baseline = y + h - strip - 11 - (min(len(simpleSplit(name, FONT_BOLD, 8.2, w - 2 * pad)), 2) - 1) * 9.4

    c.setFillColor(MUTED)
    c.setFont(FONT, 7.0)
    line_y = baseline - 10.5
    if role.lower() != name.lower():
        c.drawCentredString(node.x, line_y, role[:34])
        line_y -= 9.0
    if dept:
        c.drawCentredString(node.x, line_y, dept[:34])

    if person.get('is_pricing'):
        c.setFillColor(HexColor('#8a6410'))
        c.setFont(FONT_BOLD, 6.2)
        c.drawCentredString(node.x, y + 4.5, 'PRICING')


def _draw_connectors(c, node):
    """Elbow connectors: down from the parent, across, down into each child."""
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
        _draw_connectors(c, child)


def _walk(node, fn):
    fn(node)
    for child in node.children:
        _walk(child, fn)


def _page_header(c, page_w, page_h, title, subtitle):
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 15)
    c.drawString(MARGIN, page_h - MARGIN - 4, title)
    if subtitle:
        c.setFillColor(MUTED)
        c.setFont(FONT, 8.6)
        c.drawString(MARGIN, page_h - MARGIN - 18, subtitle)
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.6)
    c.line(MARGIN, page_h - MARGIN - 26, page_w - MARGIN, page_h - MARGIN - 26)


def _render_tree(c, root, page_w, page_h, title, subtitle):
    """One subtree per page, scaled only if it genuinely cannot fit."""
    measure(root)
    place(root, 0, 0)

    xs, ys = [], []
    _walk(root, lambda n: (xs.append(n.x), ys.append(n.y)))
    min_x, max_x = min(xs) - BOX_W / 2.0, max(xs) + BOX_W / 2.0
    min_y, max_y = min(ys) - BOX_H, max(ys)

    content_w = max(max_x - min_x, 1.0)
    content_h = max(max_y - min_y, 1.0)
    avail_w = page_w - 2 * MARGIN
    avail_h = page_h - 2 * MARGIN - 40

    # Fill the sheet: shrink a wide branch, but also enlarge a small one rather
    # than stranding three boxes in the corner of an A3 page.
    scale = min(avail_w / content_w, avail_h / content_h)
    scale = max(0.45, min(scale, 2.0))

    _page_header(c, page_w, page_h, title, subtitle)
    c.saveState()
    # Centre on both axes within the area below the header.
    c.translate(MARGIN + (avail_w - content_w * scale) / 2.0,
                MARGIN + (avail_h - content_h * scale) / 2.0 - (min_y * scale))
    c.scale(scale, scale)
    c.translate(-min_x, 0)
    _draw_connectors(c, root)
    _walk(root, lambda n: _draw_box(c, n, scale))
    c.restoreState()

    c.setFillColor(MUTED)
    c.setFont(FONT, 7.4)
    if scale < 0.999:
        c.drawRightString(page_w - MARGIN, MARGIN - 12,
                          'scaled to %d%% to fit' % round(scale * 100))
    c.showPage()


def build(people, title='Organisation chart', subtitle=''):
    """Return the chart as PDF bytes."""
    from io import BytesIO

    page_w, page_h = landscape(A3)
    buffer = BytesIO()
    c = pdfcanvas.Canvas(buffer, pagesize=(page_w, page_h))
    c.setTitle(title)

    roots = build_forest(people)
    if not roots:
        _page_header(c, page_w, page_h, title, 'Nobody has been placed yet.')
        c.showPage()
        c.save()
        return buffer.getvalue()

    for root in roots:
        person = root.person
        root_name = person.get('name') or 'Organisation'

        # Overview page: the top of the house and who reports straight into it.
        if root.children:
            overview = Node(person)
            overview.children = [Node(child.person) for child in root.children]
            _render_tree(c, overview, page_w, page_h, title,
                         '%s  ·  %s' % (root_name, subtitle) if subtitle else root_name)

            # Then a page per branch that actually has people under it.
            for child in root.children:
                if not child.children:
                    continue
                _render_tree(
                    c, child, page_w, page_h,
                    child.person.get('rbac_department_name') or child.person.get('name'),
                    '%s  ·  reports to %s' % (child.person.get('name'), root_name))
        else:
            _render_tree(c, root, page_w, page_h, title, subtitle)

    c.save()
    return buffer.getvalue()
