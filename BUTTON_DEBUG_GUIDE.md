# Inventory Buttons Debugging Guide

## Issue
Plus icon (+) and Edit icon (pencil) buttons in inventory table don't open modals when clicked.

## Debugging Steps

### Step 1: Open Browser Console
1. Press **F12** to open Developer Tools
2. Go to **Console** tab
3. Clear the console (trash icon)
4. Refresh the page (Ctrl+R or Cmd+R)

### Step 2: Check for JavaScript Errors on Page Load

Look for any of these errors:
```
❌ Uncaught ReferenceError: formatNumber is not defined
❌ Uncaught ReferenceError: escapeHtml is not defined  
❌ Uncaught ReferenceError: Swal is not defined
❌ Uncaught TypeError: Cannot read property 'DataTable' of undefined
```

If you see **any** errors, note them down.

### Step 3: Verify Libraries Are Loaded

In the console, type these commands and press Enter after each:

```javascript
// Check jQuery
typeof jQuery
// Should return: "function"

// Check DataTables
typeof $.fn.DataTable
// Should return: "function"

// Check SweetAlert2
typeof Swal
// Should return: "object"

// Check if functions exist
typeof formatNumber
// Should return: "function"

typeof escapeHtml
// Should return: "function"

typeof showAddStockModal
// Should return: "function"

typeof editInventoryItem
// Should return: "function"
```

### Step 4: Test Button Click Detection

After the page loads, click the **Plus (+) button** on any inventory item row.

**Look in console for:**
```
Add Stock button clicked for item: <number> <name>
showAddStockModal called with: <number> <name>
Swal available: true
```

If you see:
- ❌ **No console output** → Event handler not attached
- ❌ **"Swal available: false"** → SweetAlert2 not loaded
- ❌ **Alert popup** saying "SweetAlert2 is not loaded!" → Library loading issue

### Step 5: Test Edit Button

Click the **Edit (pencil) button** on any inventory item row.

**Look in console for:**
```
Edit button clicked for item: <number>
editInventoryItem called with: <number>
Swal available: true
API response: {success: true, items: [...]}
Found item: {id: X, item_name: "...", ...}
```

### Step 6: Check Network Tab

1. Go to **Network** tab in Developer Tools
2. Filter by **XHR**
3. Click a button
4. Look for:
   - `GET /api/inventory/items` - Should return 200 OK
   - Check the Response tab to see the data

### Step 7: Manual Test in Console

Try calling functions directly in the console:

```javascript
// Test Add Stock modal (replace 1 with actual item ID)
showAddStockModal(1, 'Test Item');

// Test Edit modal (replace 1 with actual item ID)
editInventoryItem(1);

// Test View modal (replace 1 with actual item ID)
viewItemDetails(1);
```

If these work directly but not via buttons, it's an event handler issue.

## Common Issues and Solutions

### Issue 1: "Swal is not defined"
**Symptom:** Console shows `Uncaught ReferenceError: Swal is not defined`

**Solution:**
1. Check if SweetAlert2 CDN is blocked
2. Try different CDN:
```html
<!-- Replace the current SweetAlert2 script with: -->
<script src="https://unpkg.com/sweetalert2@11"></script>
```

### Issue 2: Buttons Don't Respond
**Symptom:** No console output when clicking buttons

**Possible Causes:**
1. **DataTables interfering with events** - Event handlers may need to be reattached after table initialization
2. **Z-index issues** - Modal might be opening behind other elements
3. **Event propagation stopped** - Some other code might be preventing clicks

**Solutions to Try:**

**A. Check if buttons are actually clickable:**
```javascript
// In console, try:
$('.btn-add-stock').length
// Should return: number of Add Stock buttons (e.g., 10)

$('.btn-edit-item').length  
// Should return: number of Edit buttons (e.g., 10)
```

**B. Manually attach click handler:**
```javascript
// In console after page loads:
$(document).on('click', '.btn-add-stock', function() {
    console.log('Manual handler triggered');
    alert('Button clicked! ID: ' + $(this).data('id'));
});
```

Then click a button. If alert shows, event delegation works.

### Issue 3: Modal Opens But Is Hidden
**Symptom:** Console logs show function called, but no visual modal

**Solution:** Check z-index in console:
```javascript
// Check SweetAlert2 container z-index
$('.swal2-container').css('z-index');
// Should be very high (99999)

// Force it higher if needed:
$('.swal2-container').css('z-index', '999999');
```

### Issue 4: DataTable Initialization Timing
**Symptom:** Buttons work on page load but stop working after refresh

**Solution:** Event handlers must be attached AFTER DataTable initializes.

Check the order in `loadInventoryItems()`:
```javascript
// Correct order:
1. Append rows to tbody
2. Destroy existing DataTable
3. Initialize new DataTable
4. Event handlers already attached with $(document).on()
```

## Expected Working Flow

1. **Page loads** → `$(document).ready()` fires
2. **loadInventoryItems()** called → Fetches data from API
3. **Rows appended** → Buttons created with classes `.btn-add-stock`, `.btn-edit-item`
4. **DataTable initialized** → Table becomes sortable/searchable
5. **User clicks button** → Event bubbles up to `document`
6. **$(document).on('click', '.btn-add-stock')** catches event
7. **showAddStockModal()** called → SweetAlert2 modal opens
8. **User fills form** → Data submitted via AJAX
9. **Success callback** → Swal success message, table refreshes

## Quick Fix Attempts

### Fix 1: Verify Script Load Order
Check that scripts are in this order in `item_management.html`:
```html
1. jQuery (from main.html template)
2. DataTables JS
3. Select2 JS
4. SweetAlert2 JS  ← MUST be before custom scripts
5. Custom JavaScript (inline <script> block)
```

### Fix 2: Force SweetAlert2 to Load
Add this at the very top of your JavaScript block:
```javascript
$(document).ready(function() {
    // Wait for SweetAlert2 to load
    if (typeof Swal === 'undefined') {
        console.error('SweetAlert2 not loaded! Waiting...');
        setTimeout(function() {
            if (typeof Swal === 'undefined') {
                alert('CRITICAL: SweetAlert2 failed to load. Modals will not work.');
            }
        }, 2000);
    }
    
    // Rest of your code...
});
```

### Fix 3: Use Bootstrap Modal Instead (Fallback)
If SweetAlert2 won't load, you can use Bootstrap modals instead:

```javascript
function showAddStockModal(itemId, itemName) {
    if (typeof Swal === 'undefined') {
        // Fallback to Bootstrap modal
        $('#addTransactionModal').modal('show');
        $('#transItemSelect').val(itemId).trigger('change');
        return;
    }
    // Normal Swal code...
}
```

## Test Checklist

Run through this checklist:

- [ ] Page loads without JavaScript errors
- [ ] Console shows: "Item Management page loaded"
- [ ] Inventory table displays with data
- [ ] All three buttons visible in Actions column
- [ ] Clicking View button → Modal opens (Bootstrap modal)
- [ ] Clicking Plus button → Console shows "Add Stock button clicked"
- [ ] Clicking Plus button → SweetAlert2 modal opens
- [ ] Clicking Edit button → Console shows "Edit button clicked"
- [ ] Clicking Edit button → SweetAlert2 modal opens with form
- [ ] Filling form and clicking Save → API call made
- [ ] Success → Table refreshes with updated data

## Report Template

If issues persist, provide this information:

```
BROWSER: [Chrome/Firefox/Safari/Edge] Version: [XX]
OS: [Windows/Mac/Linux]

CONSOLE ERRORS ON PAGE LOAD:
[Paste any errors here]

LIBRARY STATUS:
typeof jQuery: [result]
typeof Swal: [result]
typeof $.fn.DataTable: [result]

BUTTON CLICK TEST (Plus Icon):
Console output: [paste output or "no output"]
Modal appeared: [Yes/No]

BUTTON CLICK TEST (Edit Icon):
Console output: [paste output or "no output"]
Modal appeared: [Yes/No]

MANUAL FUNCTION TEST:
showAddStockModal(1, 'Test'):
  Result: [Modal opened / Error / No response]

editInventoryItem(1):
  Result: [Modal opened / Error / No response]

NETWORK TAB:
GET /api/inventory/items status: [200/404/500/etc]
Response data: [Has items: Yes/No]
```

## Next Steps

After running through this guide:

1. **If all tests pass but buttons don't work** → Event delegation issue
2. **If Swal is undefined** → CDN or loading issue
3. **If functions don't exist** → Script compilation error
4. **If API returns error** → Backend issue

Share the console output and we'll identify the exact problem!
