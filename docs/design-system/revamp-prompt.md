# UI/UX And Design System Revamp Prompt

Use this prompt to revamp another internal business system with the same approach used for Branding Gate.

```text
You are a senior product designer and frontend engineer. Read this project deeply before changing code.

Goal:
Revamp the full UI/UX and create a reusable design system that every current and future page must follow.

Design Direction:
- Build a dense enterprise admin design system inspired by Carbon for data-heavy screens, Polaris for admin workflows, Stripe for finance/form polish, and practical Bootstrap compatibility.
- Prioritize tables, filters, actions, modals, drawers, approvals, finance values, and mobile usability.
- Do not make a marketing-style redesign. This is an operational system for repeated daily work.

Required Process:
1. Audit the app structure, templates, shared layout, CSS, tables, modals, forms, and page inheritance.
2. Identify the shared shell or layout file that all pages inherit.
3. Create one global design-system CSS layer with tokens, components, and compatibility overrides.
4. Wire the design-system CSS into the shared shell after existing page styles so it wins safely.
5. Add reusable template/components/helpers only where the framework already supports them.
6. Revamp current pages through shared styles first. Avoid page-by-page rewrites unless a page has unique behavior.
7. Make all tables mobile-friendly and horizontally usable:
   - table wrapper width 100%
   - horizontal overflow
   - sticky headers
   - compact rows
   - drag-to-scroll for mouse/pointer users
   - native touch scrolling
   - actions remain reachable
8. For very complex data pages, prefer drawers or detail pages over giant nested modals.
9. Preserve all existing functions and endpoints. Do not break CRUD, filters, exports, buttons, modals, or role-based behavior.
10. Add the smallest regression check that proves the design system is wired globally.
11. Restart the service after changes and verify the app responds.

Design Tokens:
- brand primary, hover, accent, warm, danger
- page, surface, muted surface
- border, strong border
- text, muted text, soft text
- success, warning, info, danger, neutral status colors
- radius and shadow tokens
- focus ring token

Component Requirements:
- shared page shell
- page header
- toolbar/action area
- cards
- forms and focus states
- buttons
- badges/status pills
- responsive table shell
- DataTables compatibility
- modals
- detail drawer pattern
- mobile rules

Table Standard:
Use a shared table wrapper/component for future pages:

<div class="table-responsive">
  <table class="table table-hover bg-data-table">
    ...
  </table>
</div>

For large tables, define explicit column widths with colgroup or DataTables column widths so headers and cells align.

Deliverables:
- design-system CSS file
- reusable components/macros/helpers if the framework supports them
- documentation explaining principles, page pattern, table pattern, modal/drawer rules, and tokens
- regression test or smoke check proving every full page inherits the shared shell
- service restart and verification notes

Constraints:
- Reuse existing framework and dependencies.
- Do not add a new UI library unless the project already uses it.
- Keep the diff small and centralized.
- Avoid speculative abstractions.
- Fix root causes in shared code, not individual symptoms page by page.
```

## Suggested Techniques

- Use one late-loaded CSS layer for tokens and compatibility overrides.
- Keep tokens semantic: `--brand-primary`, `--surface`, `--status-success`, not page names.
- Put table behavior in the shared shell so injected tables and modal tables inherit it.
- Use `pointerdown`/`pointermove` with pointer capture for drag-to-scroll.
- Exclude interactive controls from drag handlers: buttons, links, inputs, selects, textareas, labels, dropdown menus.
- Prefer full-width pages for dense table screens.
- Use `colgroup` or DataTables `columns.width` for wide important tables.
- Use CSS media queries for mobile cards only on the few tables that need card layouts.
- Use drawers/detail pages for nested tables instead of tables inside tables inside modals.
- Add one regression test that checks the design CSS, shared shell, table drag behavior, and page inheritance.
