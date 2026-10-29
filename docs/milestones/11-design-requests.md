# 11 - Design Requests

**Goal:** Sales and Account Management ask Design for work through the
system: shared header, category tabs with their own fields, attachments;
Design assigns a designer, the designer uploads the work, the Design Manager
approves, and the requester sends it to Operation. The 2D and 3D Design
portals open on this list. Spec: `docs/PRD.md`, "Design Requests".

**Acceptance:**
- `tests/test_design_requests.py` passes (flow, refusals, fields, scope, files).
- Browser at 390px and 1440px: full flow as requester, design head,
  designer, Design Manager, requester again; Operations sees it after send.

**Status:** live 2026-10-28. Suite 815 OK; browser flow at 1440px (Sarah) and 390px (Gamal, Mayar, David in Arabic). Mayar Eid created; Gamal holds assign and approve as user grants. Waiting on: the 3D map (3D uses the 2D categories meanwhile).

**Round 2 (Gamal, 2026-10-30):** several brief files per item from different
folders; work, submit and approval per item; job code (Sales Request) on the
header; Operations gets each item's final round only. Acceptance:
`tests/test_design_requests.py` (per-item flow, rounds, Operation file gate,
job code, several files). Status: live 2026-10-30.
