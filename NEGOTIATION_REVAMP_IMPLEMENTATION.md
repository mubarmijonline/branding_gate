# Negotiation Workflow Revamp - Implementation Guide

## ✅ Completed Tasks

### 1. Database Schema ✅
Created two new tables:

**`negotiation_requests`** - Main negotiation tracking
- `id`: Primary key
- `item_id`: Foreign key to sales_request_items
- `request_id`: Foreign key to sales_request
- `client_expected_price`: DECIMAL - Client's desired price
- `client_reason`: TEXT - Client's negotiation reason
- `status`: ENUM - Workflow status (pending_sales_head, sales_head_approved, etc.)
- `sales_head_decision`: ENUM - Sales head's decision
- `sales_head_notes`: TEXT - Notes from sales head
- `sales_head_user_id`: INT - Who approved/declined
- `sales_head_decision_date`: DATETIME
- `new_cost_price`: DECIMAL - New pricing from pricing team
- `new_selling_price`: DECIMAL - New selling price from sales
- Timestamps: created_at, updated_at

**`negotiation_logs`** - Audit trail
- `id`: Primary key
- `negotiation_id`: Foreign key to negotiation_requests
- `action`: VARCHAR - Action taken
- `actor_user_id`: INT - Who performed action
- `actor_name`: VARCHAR - Name of actor
- `notes`: TEXT - Action notes
- `old_price`: DECIMAL
- `new_price`: DECIMAL
- `created_at`: DATETIME

### 2. Sales Head Approval Page ✅
**File**: `/templates/sales_head_approval.html`

Features:
- ✅ Modern, clean UI with gradient header
- ✅ Statistics cards (Pending, Approved Today, Declined Today, Savings)
- ✅ Filter by status, client, date range
- ✅ Negotiation cards showing:
  - Item details
  - Client's expected price
  - Current selling price
  - Price difference & percentage
  - Client's reason
  - Approve/Decline buttons
- ✅ Approve modal (sends to Pricing Team)
- ✅ Decline modal (returns to Client Approval)
- ✅ Auto-refresh functionality
- ✅ Empty state handling

### 3. Client Approval Page Updates ✅
**File**: `/templates/client_approval.html`

Updates:
- ✅ Enhanced negotiation modal with:
  - Current price display
  - Expected price input field
  - Negotiation reason textarea
  - Workflow indication (routes to Sales Head)
- ✅ Updated `negotiateItem()` function to include expected_price
- ✅ Added current-price data attribute to negotiate button
- ✅ Improved success message with workflow steps

---

## 🔨 Pending Implementation

### 4. Backend Routes (branding_gate.py) - **NEEDS IMPLEMENTATION**

#### Routes to Add:

```python
# Sales Head Routes
@app.route('/api/sales-head/negotiations', methods=['GET'])
def get_sales_head_negotiations():
    """Get all negotiation requests for sales head review"""
    # Filter by status, client_id, date_range
    # Return negotiations with item details, prices, client info
    pass

@app.route('/api/sales-head/negotiations/statistics', methods=['GET'])
def get_sales_head_statistics():
    """Get statistics for sales head dashboard"""
    # Return counts for pending, approved_today, declined_today, potential_savings
    pass

@app.route('/api/sales-head/negotiations/<int:negotiation_id>/approve', methods=['POST'])
def approve_sales_head_negotiation(negotiation_id):
    """Approve negotiation - send to pricing team"""
    # Update status to 'pending_pricing'
    # Create log entry
    # Update item approval_status to 'pending_negotiation'
    # Send notification to operations/pricing team
    pass

@app.route('/api/sales-head/negotiations/<int:negotiation_id>/decline', methods=['POST'])
def decline_sales_head_negotiation(negotiation_id):
    """Decline negotiation - return to client approval"""
    # Update status to 'sales_head_declined'
    # Update item approval_status back to 'pending'
    # Create log entry
    # Send notification to sales user
    pass

# Updated Client Approval Route
@app.route('/api/client-approval/items/<int:item_id>/negotiate', methods=['POST'])
def negotiate_item_price(item_id):
    """Create negotiation request with expected price"""
    # Get expected_price and reason from request
    # Create negotiation_requests entry with status='pending_sales_head'
    # Create initial log entry
    # Update item approval_status to 'pending_negotiation'
    # Increment negotiation_count
    pass
```

### 5. Operation Request Page Updates - **NEEDS IMPLEMENTATION**
**File**: `/templates/operation_request.html`

Required Changes:
- Add filter for negotiation items
- Show negotiation badge/indicator
- Display client expected price in costing modal
- Show negotiation history/logs
- Add special handling for negotiation items
- After pricing, route to sales for selling price

### 6. Sales Request Page Updates - **NEEDS IMPLEMENTATION**
**File**: `/templates/sales_request.html`

Required Changes:
- Add filter for "Pending Selling Price from Negotiation"
- Show negotiation context when setting selling price
- Display:
  - Client expected price
  - New cost price from pricing team
  - Suggested profit margin
  - Negotiation history
- After setting selling price, return item to "Pending Client Approval"
- Create log entry for new pricing

### 7. Navigation & Access Control - **NEEDS IMPLEMENTATION**

Add to `main.html` navigation:
```html
{% if 'sales_head' in session.get('roles', []) %}
<li class="nav-item">
    <a class="nav-link" href="/sales-head-approval">
        <i class="fas fa-user-tie"></i>
        <span>Sales Head Approval</span>
        <span class="badge badge-warning" id="pendingNegotiationsCount">0</span>
    </a>
</li>
{% endif %}
```

### 8. Email Notifications - **OPTIONAL**

Trigger emails at:
- Negotiation submitted → Sales Head
- Sales Head approved → Pricing Team
- Sales Head declined → Original Sales User
- New pricing added → Sales User
- New selling price added → Original Sales User (Client approval ready)

---

## Workflow Summary

```
1. CLIENT APPROVAL PAGE
   ↓ (Sales user clicks "Negotiate")
   ↓ Enters: Expected Price + Reason
   ↓
2. SALES HEAD APPROVAL PAGE
   ↓ (Sales Head reviews)
   ├─→ APPROVE → 3. OPERATIONS/PRICING
   │              ↓ (Pricing team adds new cost)
   │              ↓
   │            4. SALES REQUEST PAGE
   │              ↓ (Sales user adds new selling price)
   │              ↓
   │            BACK TO: CLIENT APPROVAL (Pending State with new price)
   │
   └─→ DECLINE → BACK TO: CLIENT APPROVAL (Pending State with original price)
```

---

## Testing Checklist

- [ ] Create negotiation from client approval page
- [ ] Verify negotiation appears in sales head page
- [ ] Sales head approve → Item goes to pricing
- [ ] Sales head decline → Item returns to client approval
- [ ] Pricing team adds cost → Item goes to sales
- [ ] Sales adds selling price → Item returns to client approval
- [ ] All logs are recorded correctly
- [ ] Statistics update correctly
- [ ] Filters work properly
- [ ] Error handling works

---

## Next Steps

1. Implement backend routes in `branding_gate.py`
2. Add route handler in Flask app for `/sales-head-approval` page
3. Update `operation_request.html` for negotiation pricing
4. Update `sales_request.html` for negotiation selling price
5. Add navigation menu item
6. Test complete workflow end-to-end
7. Add email notifications (optional)

---

## Files Modified

- ✅ `/templates/sales_head_approval.html` (NEW)
- ✅ `/templates/client_approval.html` (UPDATED)
- ⏳ `/branding_gate.py` (PENDING)
- ⏳ `/templates/operation_request.html` (PENDING)
- ⏳ `/templates/sales_request.html` (PENDING)
- ⏳ `/templates/main.html` (PENDING - navigation)

---

## Database Tables Created

```sql
✅ negotiation_requests
✅ negotiation_logs
```

Run this to verify:
```bash
mysql -u ps -p'Aa@123456' branding_gate -e "SHOW TABLES LIKE 'negotiation%';"
```
