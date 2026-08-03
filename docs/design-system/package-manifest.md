# Branding Gate Design System Package

## Files

- `README.md`: principles, source files, page pattern, table rules, modal/drawer rules, tokens.
- `branding-gate-system.css`: global design tokens and component styles.
- `macros.html`: optional Jinja macros for page header, cards, status pills, and table shell.
- `table-drag.js`: reusable vanilla JS drag-to-scroll behavior for tables.
- `revamp-prompt.md`: prompt for applying this system to another project.
- `test_design_system.py`: small regression check from this project.

## Apply Order

1. Add the CSS after existing app/page styles.
2. Add the table drag JS after the app loads its DOM library, or use the vanilla version as-is.
3. Make pages inherit the shared shell/layout.
4. Use `.table-responsive` around tables.
5. Use explicit column widths for important wide tables.
6. Run the regression check or create an equivalent local smoke test.
