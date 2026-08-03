from dataclasses import dataclass
from pathlib import Path
from textwrap import wrap

from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
OUTPUT_PATH = BASE_DIR / "sales-request-journey-and-privileges.pdf"
FLOW_PATH = BASE_DIR / "sales-request-journey-flow.png"
LOGO_PATH = PROJECT_DIR / "static" / "img" / "branding_gate_logo.jpg"

NAVY = colors.HexColor("#173F73")
INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#526071")
LINE = colors.HexColor("#D8E0E8")

FLOW_WIDTH = 7000
FLOW_HEIGHT = 4050
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")

ROLE_STYLES = {
    "sales": {"line": "#173F73", "fill": "#E8EEF8", "lane": "#F5F8FC"},
    "admin": {"line": "#D39A2C", "fill": "#FFF7E6", "lane": "#FFFCF5"},
    "operations": {"line": "#19856F", "fill": "#E7F6F2", "lane": "#F4FBF9"},
    "pricing": {"line": "#B45309", "fill": "#FFF3E0", "lane": "#FFFAF3"},
    "sales_head": {"line": "#7750A8", "fill": "#F2ECFA", "lane": "#FAF7FD"},
    "client": {"line": "#1687A0", "fill": "#EAF5F8", "lane": "#F4FAFC"},
    "rejected": {"line": "#C94A55", "fill": "#FDECEC", "lane": "#FFF8F8"},
}

FLOW_LANES = [
    ("Sales", "sales"),
    ("Admin", "admin"),
    ("Operations", "operations"),
    ("Sales Head", "sales_head"),
    ("Client Decision", "client"),
]


@dataclass(frozen=True)
class Box:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def center_x(self):
        return (self.left + self.right) // 2

    @property
    def center_y(self):
        return (self.top + self.bottom) // 2


def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(str(FONT_DIR / name), size)


def fit_image(path, max_width, max_height):
    with PILImage.open(path) as source:
        width, height = source.size
    scale = min(max_width / width, max_height / height)
    return Image(str(path), width=width * scale, height=height * scale)


def centered_text(draw, box, text, text_font, fill="#172033", spacing=8):
    lines = text.split("\n")
    metrics = [draw.textbbox((0, 0), line, font=text_font) for line in lines]
    heights = [metric[3] - metric[1] for metric in metrics]
    total_height = sum(heights) + spacing * (len(lines) - 1)
    y = box.top + (box.bottom - box.top - total_height) / 2

    for line, metric, height in zip(lines, metrics, heights):
        width = metric[2] - metric[0]
        x = box.left + (box.right - box.left - width) / 2
        draw.text((x, y), line, font=text_font, fill=fill)
        y += height + spacing


def draw_process(draw, box, text, role, text_size=56):
    style = ROLE_STYLES[role]
    draw.rounded_rectangle(
        (box.left, box.top, box.right, box.bottom),
        radius=28,
        fill=style["fill"],
        outline=style["line"],
        width=7,
    )
    centered_text(draw, box, text, font(text_size, bold=True), spacing=7)


def draw_decision(draw, box, text, role, text_size=54):
    style = ROLE_STYLES[role]
    points = [
        (box.center_x, box.top),
        (box.right, box.center_y),
        (box.center_x, box.bottom),
        (box.left, box.center_y),
    ]
    draw.polygon(points, fill=style["fill"], outline=style["line"], width=7)
    centered_text(draw, box, text, font(text_size, bold=True), spacing=6)


def draw_arrow_label(draw, anchor, label, color="#526071"):
    label_font = font(38, bold=True)
    lines = wrap(label, width=20) or [label]
    text = "\n".join(lines)
    metrics = [draw.textbbox((0, 0), line, font=label_font) for line in lines]
    width = max(metric[2] - metric[0] for metric in metrics) + 38
    height = sum(metric[3] - metric[1] for metric in metrics) + 18 + 5 * (len(lines) - 1)
    x, y = anchor
    box = Box(int(x - width / 2), int(y - height / 2), int(x + width / 2), int(y + height / 2))
    draw.rounded_rectangle(
        (box.left, box.top, box.right, box.bottom),
        radius=14,
        fill="#FFFFFF",
        outline="#D8E0E8",
        width=2,
    )
    centered_text(draw, box, text, label_font, fill=color, spacing=5)


def draw_orthogonal_arrow(draw, points, color="#526071", label=None, label_anchor=None):
    if len(points) < 2:
        raise ValueError("An arrow requires at least two points")

    for start, end in zip(points, points[1:]):
        if start[0] != end[0] and start[1] != end[1]:
            raise ValueError(f"Non-orthogonal arrow segment: {start} -> {end}")

    draw.line(points, fill=color, width=8, joint="curve")

    previous = points[-2]
    tip = points[-1]
    if previous[0] == tip[0]:
        direction = 1 if tip[1] > previous[1] else -1
        arrowhead = [
            tip,
            (tip[0] - 18, tip[1] - 30 * direction),
            (tip[0] + 18, tip[1] - 30 * direction),
        ]
    else:
        direction = 1 if tip[0] > previous[0] else -1
        arrowhead = [
            tip,
            (tip[0] - 30 * direction, tip[1] - 18),
            (tip[0] - 30 * direction, tip[1] + 18),
        ]
    draw.polygon(arrowhead, fill=color)

    if label and label_anchor:
        draw_arrow_label(draw, label_anchor, label, color)


def generate_flow_image():
    image = PILImage.new("RGB", (FLOW_WIDTH, FLOW_HEIGHT), "#FFFFFF")
    draw = ImageDraw.Draw(image)

    lane_left = 500
    lane_right = 6940

    def draw_section_title(text, top):
        draw.text((45, top), text, font=font(62, bold=True), fill="#173F73")

    def draw_lanes(lanes, top, lane_height, lane_gap):
        centers = {}
        for index, (label, role) in enumerate(lanes):
            lane_top = top + index * (lane_height + lane_gap)
            lane_bottom = lane_top + lane_height
            centers[role] = (lane_top + lane_bottom) // 2
            style = ROLE_STYLES[role]

            draw.rounded_rectangle(
                (40, lane_top, lane_right, lane_bottom),
                radius=28,
                fill=style["lane"],
                outline="#D8E0E8",
                width=4,
            )
            draw.rounded_rectangle(
                (40, lane_top, lane_left - 25, lane_bottom),
                radius=28,
                fill=style["fill"],
                outline=style["line"],
                width=5,
            )
            centered_text(
                draw,
                Box(65, lane_top + 24, lane_left - 50, lane_bottom - 24),
                label,
                font(56, bold=True),
                fill=style["line"],
            )
        return centers

    draw_section_title("MAIN SALES REQUEST FLOW", 20)
    main_lanes = [
        ("Sales", "sales"),
        ("Admin", "admin"),
        ("Operations", "operations"),
        ("Client Decision", "client"),
    ]
    main_centers = draw_lanes(main_lanes, top=190, lane_height=430, lane_gap=18)

    sales_y = main_centers["sales"]
    admin_y = main_centers["admin"]
    operations_y = main_centers["operations"]
    client_y = main_centers["client"]

    def process_box(center_x, center_y, width=470, height=190):
        return Box(
            center_x - width // 2,
            center_y - height // 2,
            center_x + width // 2,
            center_y + height // 2,
        )

    def decision_box(center_x, center_y, width=520, height=230):
        return process_box(center_x, center_y, width, height)

    select_client = process_box(820, sales_y, width=430, height=170)
    create_request = process_box(1450, sales_y, width=500, height=170)
    urgent_decision = decision_box(2100, sales_y, width=470, height=205)
    admin_review = process_box(2750, admin_y, width=500, height=170)
    costing = process_box(3400, operations_y, width=450, height=170)
    pricing = process_box(4050, sales_y, width=450, height=170)
    proposal = process_box(4700, sales_y, width=450, height=170)
    submit = process_box(5350, sales_y, width=470, height=170)
    client_decision = decision_box(6000, client_y, width=500, height=220)
    handoff = process_box(6600, operations_y, width=440, height=170)
    rejected = process_box(6600, client_y - 105, width=380, height=145)
    negotiation_next = process_box(6600, client_y + 105, width=430, height=145)

    draw_process(draw, select_client, "Select Company\nand Client", "sales", text_size=50)
    draw_process(draw, create_request, "Create Request,\nTemplates and Items", "sales", text_size=47)
    draw_decision(draw, urgent_decision, "Start within\n5 days?", "admin", text_size=48)
    draw_process(draw, admin_review, "Urgent Request\nApproval", "admin", text_size=50)
    draw_process(draw, costing, "Add Item\nCosting", "operations", text_size=50)
    draw_process(draw, pricing, "Add Selling\nPrices", "sales", text_size=50)
    draw_process(draw, proposal, "Generate\nProposal", "sales", text_size=50)
    draw_process(draw, submit, "Submit for\nClient Approval", "sales", text_size=47)
    draw_decision(draw, client_decision, "Client\nDecision", "client", text_size=50)
    draw_process(draw, handoff, "Approved for\nOperational Handoff", "operations", text_size=42)
    draw_process(draw, rejected, "Rejected", "rejected", text_size=48)
    draw_process(draw, negotiation_next, "Continue to Negotiation\nFlow Below", "sales_head", text_size=39)

    route = "#526071"
    approve_color = ROLE_STYLES["operations"]["line"]
    reject_color = ROLE_STYLES["rejected"]["line"]
    negotiate_color = ROLE_STYLES["sales_head"]["line"]

    draw_orthogonal_arrow(
        draw,
        [(select_client.right, sales_y), (create_request.left, sales_y)],
        route,
    )
    draw_orthogonal_arrow(
        draw,
        [(create_request.right, sales_y), (urgent_decision.left, sales_y)],
        route,
    )

    draw_orthogonal_arrow(
        draw,
        [
            (urgent_decision.center_x, urgent_decision.top),
            (urgent_decision.center_x, 135),
            (costing.center_x, 135),
            (costing.center_x, costing.top),
        ],
        route,
        label="No: normal timing",
        label_anchor=(2730, 135),
    )
    draw_orthogonal_arrow(
        draw,
        [
            (urgent_decision.center_x, urgent_decision.bottom),
            (urgent_decision.center_x, admin_y),
            (admin_review.left, admin_y),
        ],
        ROLE_STYLES["admin"]["line"],
        label="Yes",
        label_anchor=(2290, admin_y),
    )
    draw_orthogonal_arrow(
        draw,
        [
            (admin_review.right, admin_y),
            (3080, admin_y),
            (3080, operations_y),
            (costing.left, operations_y),
        ],
        approve_color,
        label="Approve",
        label_anchor=(3080, 1000),
    )
    draw_orthogonal_arrow(
        draw,
        [
            (admin_review.left, admin_y),
            (2420, admin_y),
            (2420, 630),
            (create_request.center_x, 630),
            (create_request.center_x, create_request.bottom),
        ],
        reject_color,
        label="Reject and return",
        label_anchor=(1940, 630),
    )

    draw_orthogonal_arrow(
        draw,
        [
            (costing.right, operations_y),
            (3720, operations_y),
            (3720, sales_y),
            (pricing.left, sales_y),
        ],
        route,
    )
    draw_orthogonal_arrow(draw, [(pricing.right, sales_y), (proposal.left, sales_y)], route)
    draw_orthogonal_arrow(draw, [(proposal.right, sales_y), (submit.left, sales_y)], route)
    draw_orthogonal_arrow(
        draw,
        [
            (submit.right, sales_y),
            (5660, sales_y),
            (5660, client_y),
            (client_decision.left, client_y),
        ],
        route,
    )

    draw_orthogonal_arrow(
        draw,
        [
            (client_decision.center_x, client_decision.top),
            (client_decision.center_x, operations_y),
            (handoff.left, operations_y),
        ],
        approve_color,
        label="Approve",
        label_anchor=(6200, operations_y),
    )
    draw_orthogonal_arrow(
        draw,
        [
            (client_decision.right, client_y),
            (6330, client_y),
            (6330, rejected.center_y),
            (rejected.left, rejected.center_y),
        ],
        reject_color,
        label="Reject",
        label_anchor=(6325, client_y - 60),
    )
    draw_orthogonal_arrow(
        draw,
        [
            (client_decision.right, client_y),
            (6360, client_y),
            (6360, negotiation_next.center_y),
            (negotiation_next.left, negotiation_next.center_y),
        ],
        negotiate_color,
        label="Negotiate",
        label_anchor=(6360, client_y + 58),
    )

    draw_section_title("NEGOTIATION AND PRICING-OWNED DECISION FLOW", 2220)
    negotiation_lanes = [
        ("Client Decision", "client"),
        ("Sales Head", "sales_head"),
        ("Re-Pricing", "pricing"),
        ("Operations", "operations"),
    ]
    negotiation_centers = draw_lanes(negotiation_lanes, top=2390, lane_height=350, lane_gap=15)
    negotiation_client_y = negotiation_centers["client"]
    negotiation_head_y = negotiation_centers["sales_head"]
    negotiation_pricing_y = negotiation_centers["pricing"]
    negotiation_operations_y = negotiation_centers["operations"]

    client_negotiates = process_box(850, negotiation_client_y, width=500, height=145)
    head_review = process_box(1900, negotiation_head_y, width=500, height=145)
    head_decision = decision_box(2800, negotiation_head_y, width=480, height=185)
    pricing_decision = decision_box(4000, negotiation_pricing_y, width=580, height=190)
    recost = process_box(4800, negotiation_operations_y, width=440, height=145)
    reprice = process_box(5550, negotiation_pricing_y, width=440, height=145)
    return_client = process_box(6550, negotiation_client_y, width=500, height=145)

    draw_process(draw, client_negotiates, "Client Requests\nNegotiation", "client", text_size=46)
    draw_process(draw, head_review, "Sales Head Reviews\nExpected Price", "sales_head", text_size=43)
    draw_decision(draw, head_decision, "Sales Head\nApprove?", "sales_head", text_size=44)
    draw_decision(draw, pricing_decision, "Re-Pricing\nDecision", "pricing", text_size=46)
    draw_process(draw, recost, "Operations\nRe-costs", "operations", text_size=46)
    draw_process(draw, reprice, "Enter New\nSelling Price", "pricing", text_size=44)
    draw_process(draw, return_client, "Return to\nClient Review", "client", text_size=46)

    draw_orthogonal_arrow(
        draw,
        [
            (client_negotiates.right, negotiation_client_y),
            (1350, negotiation_client_y),
            (1350, negotiation_head_y),
            (head_review.left, negotiation_head_y),
        ],
        negotiate_color,
    )
    draw_orthogonal_arrow(
        draw,
        [(head_review.right, negotiation_head_y), (head_decision.left, negotiation_head_y)],
        negotiate_color,
    )
    draw_orthogonal_arrow(
        draw,
        [
            (head_decision.center_x, head_decision.top),
            (head_decision.center_x, 2400),
            (6200, 2400),
            (6200, negotiation_client_y),
            (return_client.left, negotiation_client_y),
        ],
        reject_color,
        label="Sales Head declines",
        label_anchor=(4450, 2400),
    )
    draw_orthogonal_arrow(
        draw,
        [
            (head_decision.right, negotiation_head_y),
            (3400, negotiation_head_y),
            (3400, negotiation_pricing_y),
            (pricing_decision.left, negotiation_pricing_y),
        ],
        negotiate_color,
        label="Approve: always to Re-Pricing",
        label_anchor=(3400, 3110),
    )
    draw_orthogonal_arrow(
        draw,
        [
            (pricing_decision.right, negotiation_pricing_y),
            (reprice.left, negotiation_pricing_y),
        ],
        ROLE_STYLES["pricing"]["line"],
        label="Re-Price Directly",
        label_anchor=(4800, negotiation_pricing_y),
    )
    draw_orthogonal_arrow(
        draw,
        [
            (pricing_decision.center_x, pricing_decision.bottom),
            (pricing_decision.center_x, negotiation_operations_y),
            (recost.left, negotiation_operations_y),
        ],
        approve_color,
        label="Re-Cost First",
        label_anchor=(4300, negotiation_operations_y),
    )
    draw_orthogonal_arrow(
        draw,
        [
            (pricing_decision.center_x, pricing_decision.top),
            (pricing_decision.center_x, 2750),
            (return_client.center_x, 2750),
            (return_client.center_x, return_client.top),
        ],
        reject_color,
        label="Pricing declines",
        label_anchor=(5250, 2750),
    )
    draw_orthogonal_arrow(
        draw,
        [
            (recost.right, negotiation_operations_y),
            (5200, negotiation_operations_y),
            (5200, reprice.bottom),
            (reprice.center_x, reprice.bottom),
        ],
        approve_color,
        label="Updated cost returns to Re-Pricing",
        label_anchor=(5200, 3480),
    )
    draw_orthogonal_arrow(
        draw,
        [
            (reprice.right, negotiation_pricing_y),
            (6550, negotiation_pricing_y),
            (6550, return_client.bottom),
        ],
        ROLE_STYLES["pricing"]["line"],
        label="Revised price",
        label_anchor=(6200, negotiation_pricing_y),
    )

    image.save(FLOW_PATH, quality=96)


def page_header_footer(canvas, document):
    canvas.saveState()
    page_width, _ = landscape(A3)
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.line(15 * mm, 13 * mm, page_width - 15 * mm, 13 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(15 * mm, 8.5 * mm, "Branding Gate | Sales Request")
    canvas.drawRightString(page_width - 15 * mm, 8.5 * mm, f"Page {document.page}")
    canvas.restoreState()


def paragraph(value, style):
    return Paragraph(value, style)


def build_pdf():
    generate_flow_image()
    page_width, page_height = landscape(A3)
    document = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=(page_width, page_height),
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=18 * mm,
        title="Sales Request Flowchart and Section Controls",
        author="Branding Gate",
        subject="Sales Request journey and role controls",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="DocumentTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=25,
        leading=29,
        textColor=NAVY,
        alignment=TA_LEFT,
        spaceAfter=2 * mm,
    ))
    styles.add(ParagraphStyle(
        name="Subtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=MUTED,
        spaceAfter=3 * mm,
    ))
    styles.add(ParagraphStyle(
        name="SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=NAVY,
        spaceAfter=3 * mm,
    ))
    styles.add(ParagraphStyle(
        name="TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.7,
        leading=10.5,
        textColor=colors.white,
    ))
    styles.add(ParagraphStyle(
        name="TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=10.5,
        textColor=INK,
    ))
    styles.add(ParagraphStyle(
        name="TableCellStrong",
        parent=styles["TableCell"],
        fontName="Helvetica-Bold",
        textColor=NAVY,
    ))

    logo = fit_image(LOGO_PATH, 25 * mm, 25 * mm)
    title_block = [
        paragraph("Sales Request Flowchart", styles["DocumentTitle"]),
        paragraph(
            "Role-owned process from request creation through client decision and operational handoff",
            styles["Subtitle"],
        ),
    ]
    header = Table([[logo, title_block]], colWidths=[31 * mm, 340 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    story = [header, Spacer(1, 2 * mm)]
    story.append(fit_image(FLOW_PATH, document.width, 225 * mm))
    story.append(PageBreak())

    story.append(paragraph("Sales Request Section Controls", styles["SectionTitle"]))
    story.append(paragraph(
        "Roles shown below reflect who can control each Sales Request section. Admin acts as an override on role-protected actions.",
        styles["Subtitle"],
    ))

    headers = [
        "Sales Request section",
        "View",
        "Create",
        "Edit or act",
        "Approve or decide",
        "Restrictions",
    ]
    rows = [
        ["Request List and Details", "Sales, Admin", "-", "Sales, Admin", "-", "Read access uses the Sales Request permission."],
        ["New Sales Request", "Sales, Admin", "Sales, Admin", "Sales, Admin", "Admin for urgent dates", "Normal requests do not require approval."],
        ["Request Templates and Items", "Sales, Admin", "Sales, Admin", "Sales, Admin", "-", "Costed items cannot be removed or materially changed."],
        ["Urgent Request Approval", "Admin", "Sales submits", "Admin", "Admin", "Required when a non-admin request starts within five days."],
        ["Costing", "Operations, Admin", "-", "Operations, Admin", "Operations owns cost", "Costing is separate from selling-price entry."],
        ["Selling Price and Re-pricing", "Sales, Pricing/Operations, Admin", "-", "Sales, Pricing/Operations, Admin", "Pricing owns negotiation pricing", "Re-pricing returns the item to client review."],
        ["Proposal Generation", "Sales, Admin", "-", "Sales, Admin", "Sales confirms", "Only eligible costed and priced items appear in the proposal."],
        ["Client Approval Submission", "Sales, Admin", "-", "Sales, Admin", "Sales submits", "Both cost and selling price are required before submission."],
        ["Client Approve, Reject and Negotiate", "Sales, Admin", "-", "Sales records decision", "Client decision", "There is no external Client login; Sales records the outcome."],
        ["Sales Head Negotiation Review", "Sales Head, Admin", "-", "Sales Head, Admin", "Sales Head", "May decline or approve; approval always sends to Re-Pricing."],
        ["Pricing Negotiation Decision", "Pricing/Operations, Admin", "-", "Pricing/Operations, Admin", "Pricing", "Chooses Re-Price Now, Re-Cost First, or Decline."],
        ["Negotiation Re-Costing", "Operations, Admin", "-", "Operations, Admin", "Operations owns cost", "Available only after Pricing requests re-costing; returns to Pricing."],
        ["Comments and Mentions", "Sales, Admin", "Sales, Admin", "Author or Admin", "-", "Comments remain attached to the Sales Request context."],
        ["Change Log and Workflow Timeline", "Sales, Admin", "System generated", "-", "-", "Records edits, costing, pricing, approvals and status changes."],
        ["Request Status Control", "Sales, Admin", "-", "Admin", "Admin", "Manual request-level status changes are Admin controlled."],
        ["Approved-item Operational Handoff", "Operations, Admin", "-", "Operations, Admin", "Client approval required", "Only approved items move to Operations."],
    ]

    table_data = [[paragraph(value, styles["TableHeader"]) for value in headers]]
    for row in rows:
        table_data.append([
            paragraph(row[0], styles["TableCellStrong"]),
            *[paragraph(value, styles["TableCell"]) for value in row[1:]],
        ])

    matrix = Table(
        table_data,
        colWidths=[65 * mm, 35 * mm, 35 * mm, 47 * mm, 48 * mm, 152 * mm],
        repeatRows=1,
        hAlign="LEFT",
    )
    matrix.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.45, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FB")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(matrix)

    document.build(
        story,
        onFirstPage=page_header_footer,
        onLaterPages=page_header_footer,
    )


if __name__ == "__main__":
    build_pdf()
    print(OUTPUT_PATH)
