# Composite Items Enhancement - Nov 17, 2025

## Issues Fixed

### 1. **Duplicate item_code Error**
**Problem**: When creating a composite item, users were entering the same value (e.g., "Stage") for both `item_code` and `item_name`, causing duplicate key errors since item_code must be unique.

**Solution**: Implemented automatic item_code generation in the backend:
- If `item_code` is empty, same as `item_name`, or already exists → auto-generate new code
- Format: `INV-00001`, `INV-00002`, etc.
- Frontend now shows item_code as optional with helper text

**Files Modified**:
- `branding_gate.py` lines ~10500-10540
- `item_management.html` lines ~1383-1389

**Code Changes**:
```python
# Generate unique item_code if provided code already exists or is same as item_name
item_code = data.get('item_code')
item_name = data.get('item_name')

# Check if item_code is same as item_name or already exists
if item_code == item_name or not item_code:
    # Generate new code
    cur.execute("SELECT MAX(CAST(SUBSTRING(item_code, 5) AS UNSIGNED)) as max_num FROM inventory_items WHERE item_code LIKE 'INV-%'")
    result = cur.fetchone()
    next_num = (result['max_num'] or 0) + 1
    item_code = f'INV-{next_num:05d}'
else:
    # Check if provided code already exists
    cur.execute("SELECT id FROM inventory_items WHERE item_code = %s", (item_code,))
    if cur.fetchone():
        # Code exists, generate new one
        cur.execute("SELECT MAX(CAST(SUBSTRING(item_code, 5) AS UNSIGNED)) as max_num FROM inventory_items WHERE item_code LIKE 'INV-%'")
        result = cur.fetchone()
        next_num = (result['max_num'] or 0) + 1
        item_code = f'INV-{next_num:05d}'
```

### 2. **Component Selection Missing Dimensions**
**Problem**: When adding a composite item, the sub-item selection dropdown only showed item names, making it difficult to identify the correct items when multiple items have similar names but different dimensions.

**Solution**: Enhanced the component dropdown to display:
- Item name
- Unit of measure (PCS, M, etc.)
- Dimensions (W×H×D)
- Current stock level

**Display Format**: `Item Name (UNIT) - W×H×D [Stock: X]`

**Example**: `Wood Panel (PCS) - 120×240×18 [Stock: 50]`

**Files Modified**:
- `item_management.html` lines ~2405-2435 (`loadAvailableItems()` function)

**Code Changes**:
```javascript
response.items.forEach(function(item) {
    if (item.item_type === 'simple') {
        // Build display text with dimensions
        let displayText = item.item_name;
        
        // Add unit
        if (item.unit_of_measure) {
            displayText += ` (${item.unit_of_measure})`;
        }
        
        // Add dimensions if available
        if (item.width || item.height || item.depth) {
            const w = item.width || 0;
            const h = item.height || 0;
            const d = item.depth || 0;
            displayText += ` - ${w}×${h}×${d}`;
        }
        
        // Add stock info
        displayText += ` [Stock: ${item.quantity_in_stock}]`;
        
        select.append(`<option value="${item.id}">${displayText}</option>`);
    }
});
```

## Testing

### Test Case 1: Duplicate item_code
**Input**:
```json
{
  "item_code": "Stage",
  "item_name": "Stage",
  "item_type": "composite",
  "components": [...]
}
```

**Expected Result**:
- ✅ Item created successfully with auto-generated code (e.g., `INV-00012`)
- ✅ No duplicate key error
- ✅ item_name remains "Stage"

### Test Case 2: Empty item_code
**Input**:
```json
{
  "item_code": "",
  "item_name": "Custom Stage Setup",
  "item_type": "composite",
  "components": [...]
}
```

**Expected Result**:
- ✅ Item created with auto-generated code
- ✅ Code follows format `INV-00013`

### Test Case 3: Component Selection Display
**Action**: Open "Add Item" modal, select "Composite" type, view component dropdown

**Expected Display**:
```
Select sub-item...
Wood Panel (PCS) - 120×240×18 [Stock: 50]
Aluminum Frame (M) - 2×2×0 [Stock: 100]
LED Light Strip (PCS) - 30×5×2 [Stock: 25]
Backdrop Fabric (M2) - 0×0×0 [Stock: 200]
```

## Database Schema Reference

**Table**: `inventory_items`
- `item_code` VARCHAR(50) UNIQUE - Now auto-generated if needed
- `item_name` VARCHAR(255) - User-provided name
- `item_type` ENUM('simple', 'composite')
- `width`, `height`, `depth` DECIMAL(10,2) - Dimensions
- `unit_of_measure` VARCHAR(20)

**Table**: `inventory_item_components`
- `parent_item_id` - Composite item ID
- `component_item_id` - Simple item ID
- `quantity_required` - How many sub-items needed
- `unit_of_measure` - Unit for the component

## User Benefits

1. **No More Duplicate Errors**: System automatically handles item_code conflicts
2. **Better Item Selection**: See full specifications when choosing components
3. **Reduced Mistakes**: Stock levels visible during component selection
4. **Clearer Dimensions**: Easy to differentiate items with similar names

## API Changes

### `/api/inventory/items/add` (POST)
**Request Body Changes**:
- `item_code` is now OPTIONAL (was required)
- If provided and duplicate → auto-generated
- If empty → auto-generated
- If same as `item_name` → auto-generated

**Response**:
```json
{
  "success": true,
  "item_id": 12,
  "message": "Item added successfully"
}
```

### `/api/inventory/items` (GET)
**No changes needed** - Already returns dimension fields:
- `width`, `height`, `depth`
- `unit_of_measure`
- `quantity_in_stock`

## Next Steps

1. Test creating composite items with various scenarios
2. Verify component selection shows correct dimensions
3. Test with items that have NULL dimensions (should show `0×0×0`)
4. Consider adding dimension editing for existing items

## Related Documentation

- `INVENTORY_IMPLEMENTATION.md` - Inventory uniqueness constraints
- `.github/copilot-instructions.md` - Database schema and patterns
