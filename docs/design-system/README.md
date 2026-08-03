# Branding Gate Design System

Branding Gate uses one enterprise design layer on top of Bootstrap 4 and SB Admin 2. The system is inspired by Carbon for dense data screens, Polaris for admin workflows, and Stripe for finance/form polish.

## Source Files

- `static/css/branding-gate-system.css`: global tokens, component styling, and compatibility overrides.
- `templates/main.html`: shared authenticated shell; every app page should extend this.
- `templates/design_system/macros.html`: optional Jinja helpers for new pages.
- `templates/login.html` and `templates/register.html`: standalone auth pages that include the same design CSS.

## Principles

1. Dense business screens first. Tables, filters, actions, approvals, and financial values must scan quickly.
2. Current pages inherit the system globally. Do not add new page-only palettes unless the page has a real domain reason.
3. Future pages should use design tokens from `branding-gate-system.css`.
4. Modals are for focused work only. Do not place large editable tables inside modals.
5. Use drawers or detail pages for nested workflows.

## Page Pattern

Use this structure for new pages:

```html
{% extends "main.html" %}
{% from "design_system/macros.html" import page_header, data_card, table_shell %}
{% block body %}
<main class="bg-shell container-fluid">
  {% call page_header("Page Name", "Short page purpose", "fas fa-table") %}
    <button class="btn btn-primary"><i class="fas fa-plus mr-1"></i>Add</button>
  {% endcall %}

  {% call data_card("Records") %}
    {% call table_shell() %}
      <table class="table table-hover bg-data-table"></table>
    {% endcall %}
  {% endcall %}
</main>
{% endblock %}
```

## Tables

Use tables for index/list pages. Keep row actions compact and move secondary details into a drawer or full detail page.

Required table behavior:

- sticky header inside scrollable containers
- compact row height
- badges for statuses
- filters above the table, not hidden inside the table
- one primary action per row, secondary actions in a small action group/menu

## Modals, Drawers, And Detail Pages

Use a modal for:

- confirmation
- approve/reject reason
- quick add form with fewer than 8 fields
- one short warning or irreversible action

Use `.bg-detail-drawer` for:

- edit panels
- item costing
- quick details
- comments
- history preview

Use a full page with tabs for:

- nested tables
- files
- pricing history
- approval history
- finance ledgers
- request details

## Tokens

Use these tokens instead of raw colors:

- `--bg-brand-primary`
- `--bg-brand-accent`
- `--bg-brand-warm`
- `--bg-status-success`
- `--bg-status-warning`
- `--bg-status-info`
- `--bg-status-danger`
- `--bg-page`
- `--bg-surface`
- `--bg-border`
- `--bg-text`

## Naming

New utility and component classes should use the `bg-` prefix. This avoids collisions with Bootstrap classes and makes design-system-owned styles easy to find.
