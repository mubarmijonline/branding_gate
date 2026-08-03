# Branding Gate - AI Agent Instructions

## Architecture Overview
**Monolithic Flask app** (`branding_gate.py` ~11,500 lines) with MySQL backend, session-based auth, and role-based access control.

### Core Components
- **Sales Request Management**: Template-based item creation with JSON attributes, client approval workflow
- **Inventory System**: Simple/composite items, credit/consignment tracking, transaction history with DB triggers
- **Approval Workflows**: Multi-stage approval (internal → client → inventory), tracked via `approval_status` and logs
- **Comments System**: Firebase-backed with @mentions, source-based filtering (general, costing, operations, etc.)

## Critical Database Patterns

### 1. **Avoid Trigger Conflicts**
```python
# ❌ NEVER manually INSERT into inventory_transactions when triggers exist
# ✅ Let triggers handle balance_after and stock updates
cur.execute("INSERT INTO inventory_credit_items ...")  # Trigger auto-creates transaction
```

### 2. **Schema Normalization Issues**
- `supplier` table uses `primary_phone`, NOT `contact_mobile`
- Always alias: `s.primary_phone AS contact_mobile`
- `inventory_items.item_type` is ENUM('simple', 'composite') - force 'simple' if unsure

### 3. **JSON Attribute Extraction**
```python
# Extract dimensions from sales_request_items.attributes JSON
JSON_UNQUOTE(JSON_EXTRACT(i.attributes, '$.width'))
# Fallback to item_catalog via foreign key
COALESCE(JSON_EXTRACT(...), ic.width)
```

## Authentication & Authorization
- Session-based: Check `'user_id' in session` before DB ops
- Role decorator: `@role_required('admin')` or `('sales')`
- MySQL DictCursor for dict-like row access

## Key Workflows

### Inventory from Sales Approval
1. Sales item gets `approval_status='approved'` by client
2. Admin calls `/api/inventory/items/create-from-sales` with `sales_item_id`
3. Parse JSON attributes for width/height/depth/specifications
4. Generate `item_code='INV-xxxxx'`, calculate `expected_profit_per_unit`
5. Insert into `inventory_items` with `item_type='simple'`
6. **NEVER** manually insert transaction - trigger handles it

### Credit/Consignment Items
- Insert into `inventory_credit_items` only
- Triggers auto-update `inventory_transactions` and `inventory_items.quantity_in_stock`
- Use `LEFT JOIN` for resilient queries when item relationships may be missing

## Development Commands
```bash
# Run app (HTTPS on port 4008)
python branding_gate.py

# Database access
mysql -u ps -p'Aa@123456' branding_gate

# Check triggers (common debugging)
SHOW TRIGGERS LIKE 'inventory_transactions';
```

## Common Pitfalls
1. **Hanging/Performance**: Copilot indexing large dirs (`branding_gate_VENV`, `static/selectize.js-master`). Use `.copilotignore`.
2. **Column Errors**: Always verify supplier/client schema - use `SHOW COLUMNS FROM supplier`.
3. **ENUM Violations**: `item_type` must be 'simple' or 'composite', nothing else.
4. **Trigger Loops**: AFTER INSERT triggers can't UPDATE the same table - use BEFORE INSERT with `SET NEW.column`.

## File Organization
- `branding_gate.py`: All backend logic (routes, DB, auth)
- `templates/*.html`: Jinja2 templates with inline JS
- `static/`: CSS/JS/images (large vendor libs excluded from Copilot)
- `*.sql`: Schema migrations (keep as reference, don't auto-run)

## Testing Approach
- Manual testing via browser (no automated test suite)
- Check MySQL trigger behavior: `SELECT * FROM inventory_transactions ORDER BY id DESC LIMIT 10;`
- Debug prints: `print(f"DEBUG: {variable}")` throughout codebase
