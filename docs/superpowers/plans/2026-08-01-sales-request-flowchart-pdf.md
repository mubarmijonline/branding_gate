# Sales Request Flowchart PDF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a two-page A3 landscape PDF containing a large, clear Sales Request flowchart and a section-by-section role-control matrix.

**Architecture:** Replace the current six-panel flow image with a data-driven swimlane flowchart rendered by Pillow at high resolution. Keep PDF composition in ReportLab, dedicate page one to the flowchart, and restrict page two to Sales Request role controls. Add a focused verification test that builds the document and checks its PDF page count, A3 dimensions, required text, and nonblank rendered pages.

**Tech Stack:** Python 3, Pillow 12, ReportLab 4, Poppler command-line tools (`pdfinfo`, `pdftotext`, `pdftoppm`).

## Global Constraints

- The PDF contains exactly two A3 landscape pages.
- Page 1 is a large Sales Request flowchart with Sales, Admin, Operations, Sales Head, and Client Decision lanes.
- Arrows use orthogonal routes and do not pass through activity boxes or labels.
- Page 2 contains only Sales Request sections and their role controls.
- The Branding Gate logo and current restrained color system are retained.
- The current generator remains reproducible from the project virtual environment.

---

### Task 1: Add PDF Contract Verification

**Files:**
- Create: `tests/test_sales_request_journey_pdf.py`
- Modify: `docs/generate-sales-request-journey-pdf.py`

**Interfaces:**
- Consumes: `docs/generate-sales-request-journey-pdf.py` as a command-line generator.
- Produces: `docs/sales-request-journey-and-privileges.pdf` and `docs/sales-request-journey-flow.png`.

- [ ] **Step 1: Write the failing PDF contract test**

```python
from pathlib import Path
import subprocess


PROJECT = Path(__file__).resolve().parents[1]
PDF = PROJECT / "docs" / "sales-request-journey-and-privileges.pdf"
GENERATOR = PROJECT / "docs" / "generate-sales-request-journey-pdf.py"


def test_sales_request_pdf_is_two_page_a3_document():
    subprocess.run(
        [str(PROJECT / "branding_gate_VENV" / "bin" / "python"), str(GENERATOR)],
        cwd=PROJECT,
        check=True,
    )
    metadata = subprocess.run(
        ["pdfinfo", str(PDF)],
        cwd=PROJECT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "Pages:           2" in metadata
    assert "Page size:       1190.55 x 841.89 pts (A3)" in metadata


def test_sales_request_pdf_contains_required_sections_only():
    text = subprocess.run(
        ["pdftotext", "-layout", str(PDF), "-"],
        cwd=PROJECT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "Sales Request Flowchart" in text
    assert "Sales Request Section Controls" in text
    assert "Urgent Request Approval" in text
    assert "Sales Head Negotiation Review" in text
    assert "Decision Rules and System Controls" not in text
    assert "Current Permission Alignment Notes" not in text
```

- [ ] **Step 2: Run the test and verify it fails against the current A4 three-page PDF**

Run: `branding_gate_VENV/bin/pytest tests/test_sales_request_journey_pdf.py -v`

Expected: FAIL because the current document has three A4 pages and the new headings do not exist.

- [ ] **Step 3: Add explicit output constants required by the test**

Update `docs/generate-sales-request-journey-pdf.py` so the command-line execution continues to generate:

```python
OUTPUT_PATH = BASE_DIR / "sales-request-journey-and-privileges.pdf"
FLOW_PATH = BASE_DIR / "sales-request-journey-flow.png"
```

- [ ] **Step 4: Keep the failing test in place for Task 2**

Run: `branding_gate_VENV/bin/pytest tests/test_sales_request_journey_pdf.py -v`

Expected: The assertions remain red until the A3 flowchart and two-page composition are implemented.

### Task 2: Rebuild Page One as a Clear A3 Role-Lane Flowchart

**Files:**
- Modify: `docs/generate-sales-request-journey-pdf.py`
- Test: `tests/test_sales_request_journey_pdf.py`

**Interfaces:**
- Consumes: Sales Request roles and process states documented in `docs/superpowers/specs/2026-07-31-sales-request-pdf-redesign.md`.
- Produces: `generate_flow_image() -> None`, writing a high-resolution flowchart to `FLOW_PATH`.

- [ ] **Step 1: Replace stage panels with role-lane geometry**

Use a canvas of at least `6000 x 3600` pixels. Define five horizontal lanes in this order:

```python
FLOW_LANES = [
    ("Sales", "sales"),
    ("Admin", "admin"),
    ("Operations", "operations"),
    ("Sales Head", "sales_head"),
    ("Client Decision", "client"),
]
```

Place process boxes from left to right by business time. Keep each box entirely inside the responsible lane.

- [ ] **Step 2: Add orthogonal route helpers**

Implement the following drawing interface:

```python
def draw_orthogonal_arrow(draw, points, color, label=None, label_anchor=None):
    """Draw horizontal and vertical segments, then one arrowhead at the final point."""
```

All `points` pairs must share either the same x coordinate or the same y coordinate. Decision labels sit in reserved whitespace beside the branch, never over a box.

- [ ] **Step 3: Draw the normal request path**

Render these steps in chronological order:

```text
Select Company and Client
Create Request, Templates and Items
Urgent Date Decision
Operations Costing
Sales Pricing
Generate Proposal
Submit for Client Approval
Client Decision
Approved for Operational Handoff
```

Use one continuous main route and reserve the top routing channel for the non-urgent shortcut.

- [ ] **Step 4: Draw the urgent approval branch**

Route `Urgent Date Decision -> Admin Review` vertically into the Admin lane. Route `Approve` back to the main Sales path and `Reject` through a lower return channel to `Create Request, Templates and Items`.

- [ ] **Step 5: Draw the client decision and negotiation branches**

Route `Approve`, `Reject`, and `Negotiate` from the Client Decision box into three separated endpoints. Route negotiation vertically to Sales Head Review, then:

```text
Decline -> Client Review
Approve to Costing -> Operations Re-cost -> Sales Re-price -> Client Review
Approve to Pricing -> Sales Re-price -> Client Review
```

Reserve a bottom routing channel for all return-to-client paths.

- [ ] **Step 6: Make role ownership visible without a separate legend**

Each lane header names the role, and every box includes a short action label. Use stable role colors for box outlines and a neutral background for the lane itself.

- [ ] **Step 7: Run the PDF contract test**

Run: `branding_gate_VENV/bin/pytest tests/test_sales_request_journey_pdf.py -v`

Expected: Page-size assertions may still fail until Task 3, while flow image generation succeeds.

### Task 3: Compose the Two-Page A3 PDF and Role-Control Matrix

**Files:**
- Modify: `docs/generate-sales-request-journey-pdf.py`
- Modify: `docs/sales-request-journey.md`
- Test: `tests/test_sales_request_journey_pdf.py`

**Interfaces:**
- Consumes: `FLOW_PATH` from Task 2.
- Produces: a two-page A3 landscape PDF at `OUTPUT_PATH`.

- [ ] **Step 1: Change the ReportLab document to A3 landscape**

Use:

```python
from reportlab.lib.pagesizes import A3, landscape

page_width, page_height = landscape(A3)
```

Keep margins at `15 mm` or less so the flowchart uses most of page one.

- [ ] **Step 2: Dedicate page one to the flowchart**

Use the title `Sales Request Flowchart`, one short subtitle, and the flow image. Remove the introductory paragraph and all extra tables from page one.

- [ ] **Step 3: Replace pages two and three with one role-control matrix**

Use the heading `Sales Request Section Controls` and these columns:

```text
Sales Request section | View | Create | Edit or act | Approve or decide | Restrictions
```

Include the fourteen sections listed in the approved specification. Keep role names readable and use `repeatRows=1`.

- [ ] **Step 4: Update the Markdown source to match the focused PDF**

Remove general decision rules and permission-gap sections from `docs/sales-request-journey.md`. Keep only the Sales Request flow summary and section role controls.

- [ ] **Step 5: Run the complete contract test**

Run: `branding_gate_VENV/bin/pytest tests/test_sales_request_journey_pdf.py -v`

Expected: PASS with two A3 pages and all required headings.

### Task 4: Render and Visually Verify the Flowchart

**Files:**
- Verify: `docs/sales-request-journey-and-privileges.pdf`
- Verify: `docs/sales-request-journey-flow.png`

**Interfaces:**
- Consumes: final PDF and flow PNG.
- Produces: verification evidence only; no new project artifact is required.

- [ ] **Step 1: Render both PDF pages**

Run:

```bash
preview_dir=$(mktemp -d /tmp/branding-gate-sales-flow.XXXXXX)
pdftoppm -png -r 120 docs/sales-request-journey-and-privileges.pdf "$preview_dir/page"
```

Expected: exactly two PNG files.

- [ ] **Step 2: Verify both rendered pages are nonblank**

Run:

```bash
branding_gate_VENV/bin/python -c "from pathlib import Path; from PIL import Image, ImageChops; p=Path('$preview_dir'); files=sorted(p.glob('page-*.png')); assert len(files)==2; assert all(ImageChops.difference(Image.open(f).convert('RGB'), Image.new('RGB', Image.open(f).size, 'white')).getbbox() for f in files); print([Image.open(f).size for f in files])"
```

Expected: two identical A3 landscape render dimensions and no assertion failure.

- [ ] **Step 3: Inspect both pages visually**

Open both rendered pages and confirm:

```text
No arrow crosses a process box.
No arrow label overlaps a line or box.
All return paths use reserved channels.
All five role lanes are immediately identifiable.
All matrix text fits inside its cells.
```

- [ ] **Step 4: Run final metadata and text checks**

Run:

```bash
pdfinfo docs/sales-request-journey-and-privileges.pdf
pdftotext -layout docs/sales-request-journey-and-privileges.pdf -
```

Expected: two A3 pages and all required headings and role names.

## Repository Note

`/development/projects/branding_gate` is not a Git repository, so the commit steps normally required by the planning workflow cannot be performed here.
