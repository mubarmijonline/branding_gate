# Negotiation Context Display in Sales Pricing Modal

## Problem Statement
When operations completes re-costing for items that came from client negotiation, sales team needs to see the negotiation context when setting new selling prices. This ensures they understand WHY the item was re-costed and what the client's concerns were.

## Solution Implemented

### 1. Enhanced Negotiation Alert in Sales Pricing Modal

**File:** `templates/sales_request.html`
**Lines:** ~10342-10375

**Changes:**
- Upgraded from simple warning alert to detailed danger alert (matching operations page style)
- Now displays:
  - ⚠️ Re-Pricing Required header with negotiation count
  - Client's comment/reason in prominent box with border
  - Explicit instruction that operations completed re-costing
  - New total cost from operations (if available)
  - Visual hierarchy using icons, colors, and layout

**Visual Design:**
```
┌─────────────────────────────────────────────────┐
│ 🔴 ⚠️ Re-Pricing Required - Negotiation #X     │
│                                                 │
│ ┌─────────────────────────────────────────┐   │
│ │ 💬 Client's Comment:                     │   │
│ │ "Price too high - competitor offers..."  │   │
│ └─────────────────────────────────────────┘   │
│                                                 │
│ ℹ️ Operations has completed re-costing.        │
│    Please review and set updated selling price. │
│                                                 │
│ ✅ New Total Cost: EGP 1,500.00                │
└─────────────────────────────────────────────────┘
```

### 2. Preserved Negotiation Status During Operations Re-Costing

**File:** `branding_gate.py`
**Function:** `add_operation_request_costs()` (lines ~5372-5395)

**Change:**
```python
# BEFORE: Operations cleared negotiation status after re-costing
if was_negotiation:
    UPDATE ... SET approval_status = 'pending', negotiation_status = NULL

# AFTER: Keep negotiation status so sales sees the context
if was_negotiation:
    UPDATE ... SET cost_per_item = %s, total_cost = %s
    # approval_status remains 'pending_negotiation'
    # negotiation_reason remains intact
```

**Rationale:** Sales team needs to see why they're setting new prices. Keeping the negotiation flag active until they complete re-pricing provides crucial context.

### 3. Clear Negotiation Status When Sales Sets New Prices

**File:** `branding_gate.py`
**Function:** `set_item_prices()` (lines ~6893-6908, ~6992-7006)

**Changes:**
1. Added `approval_status` to SELECT query to detect negotiation items
2. Track `was_negotiation` flag based on `approval_status == 'pending_negotiation'`
3. Clear negotiation fields when sales sets new prices:

```python
if was_negotiation:
    UPDATE sales_request_items 
    SET sell_per_item = %s, total_sell = %s,
        approval_status = 'pending',         # Ready for client re-approval
        negotiation_status = NULL,           # Clear negotiation flag
        negotiation_reason = NULL            # Clear reason
    WHERE id = %s AND request_id = %s
```

**Rationale:** Once sales sets new prices addressing the negotiation, the item goes back to normal 'pending' status ready for client approval. Negotiation cycle complete.

## Complete Negotiation Workflow

```
┌────────────────────────────────────────────────────────────────────┐
│                     NEGOTIATION LIFECYCLE                          │
└────────────────────────────────────────────────────────────────────┘

1. CLIENT APPROVAL PAGE
   ├─ Client sees item with price
   ├─ Clicks "Negotiate" button
   ├─ Enters reason: "Price too high..."
   └─> Item: approval_status = 'pending_negotiation'
       negotiation_reason = "Price too high..."
       negotiation_count = 1

2. SALES HEAD APPROVAL PAGE
   ├─ Sales Head reviews negotiation request
   ├─ Approves re-costing
   └─> Negotiation status unchanged, routed to operations

3. OPERATIONS REQUEST PAGE (RE-COSTING)
   ├─ Operations sees RED BANNER with negotiation context
   │  "⚠️ Re-Costing Required - Client Negotiation #1"
   │  "Client's Comment: Price too high..."
   │
   ├─ Operations enters new cost_per_item
   ├─ System calculates new total_cost with formula
   └─> Item: approval_status = 'pending_negotiation' (KEPT)
       cost_per_item = NEW_VALUE
       total_cost = NEW_VALUE
       negotiation_reason = "Price too high..." (KEPT)

4. SALES REQUEST PAGE (RE-PRICING) ← THIS UPDATE
   ├─ Sales sees RED BANNER with negotiation context
   │  "⚠️ Re-Pricing Required - Client Negotiation #1"
   │  "Client's Comment: Price too high..."
   │  "Operations has completed re-costing"
   │  "New Total Cost: EGP X,XXX.XX"
   │
   ├─ Sales reviews new cost
   ├─ Sets new sell_per_item addressing client concern
   ├─ System calculates new total_sell with formula
   └─> Item: approval_status = 'pending' (CLEARED)
       sell_per_item = NEW_VALUE
       total_sell = NEW_VALUE
       negotiation_status = NULL (CLEARED)
       negotiation_reason = NULL (CLEARED)

5. CLIENT APPROVAL PAGE (ROUND 2)
   └─ Client sees updated price
      Option A: Accept → approval_status = 'approved'
      Option B: Negotiate again → negotiation_count++
```

## Testing Checklist

### Pre-Test Setup
1. ✅ Have a sales request with at least one item
2. ✅ Item must have cost_per_item and sell_per_item set
3. ✅ Item must be in client approval stage (approval_status = 'submitted')

### Test Steps

#### Step 1: Client Negotiation
- [ ] Go to Client Approval page
- [ ] Find an item and click "Negotiate" button
- [ ] Enter reason: "Price is 20% higher than competitor"
- [ ] Submit negotiation
- [ ] **Verify:** Item shows "NEGOTIATION #1" badge
- [ ] **Verify:** Database `approval_status = 'pending_negotiation'`

#### Step 2: Sales Head Approval
- [ ] Go to Sales Head Approval page
- [ ] Find the negotiation request
- [ ] Click "Approve for Re-costing"
- [ ] **Verify:** Status changes to approved
- [ ] **Verify:** Item still has `approval_status = 'pending_negotiation'`

#### Step 3: Operations Re-Costing
- [ ] Go to Operation Request page
- [ ] Find the request
- [ ] **Verify:** Item shows RED ALERT with:
  - "⚠️ Re-Costing Required - Client Negotiation Request #1"
  - Client's comment in bordered box
- [ ] Enter new (lower) cost_per_item
- [ ] Click "Update Costs"
- [ ] **Verify:** Database `approval_status` STILL = 'pending_negotiation'
- [ ] **Verify:** new `cost_per_item` and `total_cost` saved

#### Step 4: Sales Re-Pricing ← NEW FUNCTIONALITY
- [ ] Go to Sales Request page
- [ ] Find the request
- [ ] Click "Set Selling Prices" button
- [ ] **Verify:** Item shows RED ALERT with:
  - "⚠️ Re-Pricing Required - Client Negotiation Request #1"
  - Client's comment: "Price is 20% higher than competitor"
  - "Operations has completed re-costing"
  - "New Total Cost: EGP X,XXX.XX"
- [ ] Enter new (lower) sell_per_item
- [ ] Click "Save Prices"
- [ ] **Verify:** Database `approval_status` = 'pending' (cleared)
- [ ] **Verify:** `negotiation_status` = NULL (cleared)
- [ ] **Verify:** `negotiation_reason` = NULL (cleared)
- [ ] **Verify:** new `sell_per_item` and `total_sell` saved

#### Step 5: Client Re-Approval
- [ ] Go back to Client Approval page
- [ ] **Verify:** Item shows with new lower price
- [ ] **Verify:** NO negotiation badge (cycle complete)
- [ ] Client can now approve or negotiate again

### Database Verification Queries

```sql
-- Check item status during negotiation
SELECT id, name, approval_status, negotiation_status, negotiation_reason, 
       negotiation_count, cost_per_item, sell_per_item, total_cost, total_sell
FROM sales_request_items 
WHERE request_id = [YOUR_REQUEST_ID];

-- Check negotiation history
SELECT * FROM negotiation_requests 
WHERE request_id = [YOUR_REQUEST_ID] 
ORDER BY created_at DESC;

-- Check price history
SELECT * FROM sales_request_item_price_history 
WHERE item_id = [YOUR_ITEM_ID] 
ORDER BY created_at DESC;
```

## Technical Details

### Data Flow

**Operations adds costs (negotiation item):**
```
Input:  cost_per_item = 100
Item:   qty = 10, rental_days = 5, dimension_calc = 'WH', width = 2, height = 3

Calculate:
  effective_days = 5 (if rent + include_days=true)
  dimension_multiplier = 2 × 3 = 6
  total_cost = 100 × 10 × 5 × 6 = 30,000

UPDATE: cost_per_item = 100, total_cost = 30,000
KEEP:   approval_status = 'pending_negotiation'
KEEP:   negotiation_reason = "..."
```

**Sales sets prices (negotiation item):**
```
Input:  sell_per_item = 150
Item:   qty = 10, rental_days = 5, dimension_calc = 'WH', width = 2, height = 3

Calculate:
  effective_days = 5 (if rent + include_days=true)
  dimension_multiplier = 2 × 3 = 6
  total_sell = 150 × 10 × 5 × 6 = 45,000

UPDATE: sell_per_item = 150, total_sell = 45,000
CLEAR:  approval_status = 'pending'
CLEAR:  negotiation_status = NULL
CLEAR:  negotiation_reason = NULL
```

### Frontend Alert Styling

**CSS Classes Used:**
- `alert-danger` - Red alert for high priority
- `border-danger` - Red left border (4px)
- `bg-white` - White background for comment box
- `text-danger` - Red text
- `badge-danger` - Red badge with pulse animation
- `pulse` - CSS animation class (already exists in template)

**Icons:**
- `fa-exclamation-circle` - Warning icon (large 2x)
- `fa-comment-dots` - Comment icon
- `fa-info-circle` - Info icon
- `fa-check-circle` - Success icon (new cost)
- `fa-handshake` - Negotiation badge icon

## Files Modified

1. **templates/sales_request.html** (lines ~10342-10375)
   - Enhanced negotiation alert display
   - Added client comment, instructions, and new cost display

2. **branding_gate.py** - `add_operation_request_costs()` (lines ~5372-5395)
   - Removed clearing of negotiation status after re-costing
   - Item remains `pending_negotiation` so sales sees context

3. **branding_gate.py** - `set_item_prices()` (lines ~6893-6908, ~6992-7006)
   - Added detection of negotiation items
   - Clear negotiation fields when sales sets new prices
   - Item returns to `pending` status for client re-approval

## Benefits

1. **Full Context for Sales Team:** Sales understands WHY they're setting new prices
2. **Better Pricing Decisions:** Sales can address specific client concerns
3. **Transparent Workflow:** Each stage sees relevant information
4. **Clean State Management:** Negotiation flag cleared when complete
5. **Visual Prominence:** Red alerts ensure nobody misses negotiation items
6. **Professional UX:** Consistent styling with operations page

## Notes

- Negotiation alert only appears when `approval_status === 'pending_negotiation'`
- Alert includes actual client comment from database
- New cost from operations shown if available
- Pulse animation on badge draws attention
- Formula still applies for all cost/sell calculations
- Price history logs all changes for audit trail
