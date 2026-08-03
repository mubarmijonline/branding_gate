# Branding Gate Design System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shared Branding Gate design system that current and future pages inherit.

**Architecture:** Add one global CSS layer after SB Admin 2, document the rules, and wire it into authenticated and auth templates. Avoid framework replacement.

**Tech Stack:** Flask, Jinja, Bootstrap 4, SB Admin 2, jQuery, DataTables, plain Python assert test.

## Global Constraints

- No new frontend framework.
- No React rewrite.
- Preserve existing routes and behavior.
- Use `bg-` prefix for new design-system-owned classes.
- Keep modals for short tasks; drawers or detail pages for nested tables.

---

### Task 1: Design-System Contract

**Files:**
- Create: `tests/test_design_system.py`
- Create: `docs/design-system/README.md`
- Create: `static/css/branding-gate-system.css`
- Modify: `templates/main.html`
- Modify: `templates/login.html`
- Modify: `templates/register.html`

**Interfaces:**
- Consumes: existing Bootstrap/SB Admin classes.
- Produces: global CSS tokens and classes such as `.bg-shell`, `.bg-data-table`, and `.bg-detail-drawer`.

- [x] **Step 1: Write the failing test**

Run: `python3 tests/test_design_system.py`
Expected: fail while design assets are missing.

- [x] **Step 2: Add design-system CSS**

Create `static/css/branding-gate-system.css` with tokens, tables, buttons, forms, cards, modals, and drawer classes.

- [x] **Step 3: Add design-system documentation**

Create `docs/design-system/README.md` with page, table, modal, drawer, and token rules.

- [x] **Step 4: Wire CSS into templates**

Add `branding-gate-system.css` after `sb-admin-2.min.css` in shared and auth templates.

- [x] **Step 5: Verify**

Run: `python3 tests/test_design_system.py`
Expected: pass.
