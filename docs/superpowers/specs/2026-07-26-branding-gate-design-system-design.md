# Branding Gate Design System Design

## Goal

Create one shared design layer so current and future Branding Gate pages follow a consistent enterprise UI without rewriting the Flask/Jinja app into a new frontend stack.

## Direction

Use a Branding Gate-owned system:

- Carbon-inspired density for tables, reports, finance, and operations screens.
- Polaris-inspired admin workflow patterns for index pages, object actions, and detail navigation.
- Stripe-inspired form polish for finance, payments, validation, and confirmation states.

The system remains Bootstrap 4 compatible because the current application already depends on Bootstrap, SB Admin 2, jQuery, DataTables, and large Jinja templates.

## Architecture

Add `static/css/branding-gate-system.css` after `sb-admin-2.min.css` so it becomes the final global design layer. Document usage in `docs/design-system/README.md`. Include the CSS in `templates/main.html`, `templates/login.html`, and `templates/register.html` so authenticated pages and auth pages share the same base.

## Current Page Coverage

All pages that extend `templates/main.html` inherit:

- color tokens
- table styling
- modal styling
- form styling
- button styling
- card styling
- navbar styling
- drawer pattern classes for future replacements of complex modals

Standalone auth pages include the same CSS directly.

## Rules For Future Pages

- Extend `main.html`.
- Use `bg-` prefixed classes for new design-system-owned structure.
- Use tables for index/list views.
- Use modals only for focused, short tasks.
- Use drawers for side edits and quick detail views.
- Use full detail pages for nested tables, history, comments, files, and finance ledgers.

## Non-Goals

- No React rewrite.
- No MUI/Fluent/Carbon component package installation.
- No hand-editing every existing page into a new component hierarchy in one pass.
- No database or backend behavior changes.
