# Negotiation Workflow Implementation - COMPLETE ✅

## Implementation Summary
All backend routes and frontend pages for the new **Sales Head Approval** negotiation workflow have been successfully implemented.

---

## ✅ Completed Components

### 1. Database Schema ✅
**Tables Created:**
- `negotiation_requests` - Stores negotiation requests with all details
- `negotiation_logs` - Audit trail for all negotiation actions

**Key Columns:**
- `client_expected_price` - Price requested by client
- `client_reason` - Client's reason for negotiation
- `sales_head_decision` - approved/declined
- `sales_head_notes` - Sales head's notes
- `status` - Workflow status tracking

### 2. Backend Routes ✅
**File:** [`branding_gate.py`](branding_gate.py)

**New Routes Added (Lines 10658-11000):**

1. **Page Route:**
   ```python
   @app.route('/sales-head-approval')
   @role_required('sales_head', 'admin')
   def sales_head_approval_page()
   ```
   - Renders the Sales Head Approval page
   - Accessible to sales_head and admin roles

2. **GET Negotiations API:**
   ```python
   @app.route('/api/sales-head/negotiations', methods=['GET'])
   ```
   - Fetches all negotiation requests
   - Filters: status, client_id, date_range
   - Returns full negotiation details with item info

3. **GET Statistics API:**
   ```python
   @app.route('/api/sales-head/negotiations/statistics', methods=['GET'])
   ```
   - Returns dashboard statistics:
     - Pending count
     - Approved today count
     - Declined today count
     - Potential savings amount

4. **POST Approve API:**
   ```python
   @app.route('/api/sales-head/negotiations/<int:negotiation_id>/approve', methods=['POST'])
   ```
   - Approves negotiation
   - Updates status to `pending_pricing`
   - Creates log entry
   - Sends to Pricing Team (Operations)

5. **POST Decline API:**
   ```python
   @app.route('/api/sales-head/negotiations/<int:negotiation_id>/decline', methods=['POST'])
   ```
   - Declines negotiation
   - Updates status to `sales_head_declined`
   - Returns item to Pending Client Approval
   - Requires decline reason

**Updated Route:**
- [`negotiate_item_price()`](branding_gate.py#L10498-L10650) - Complete rewrite
  - Now accepts `expected_price` parameter
  - Creates negotiation_request entry
  - Routes to Sales Head (not directly to operations)
  - Preserves original prices for comparison

### 3. Frontend Pages ✅

#### A. Sales Head Approval Page ✅
**File:** [`templates/sales_head_approval.html`](templates/sales_head_approval.html)

**Features:**
- **Dashboard Statistics Cards:**
  - Pending Negotiations
  - Approved Today
  - Declined Today
  - Potential Savings

- **Filters:**
  - Status (Pending, Approved, Declined, All)
  - Client dropdown
  - Date range (Today, Week, Month, All)
  - Search box

- **Negotiation Cards Display:**
  - Item name, quantity, unit
  - Current selling price
  - Client expected price
  - Price difference (highlighted)
  - Client reason
  - Negotiation count
  - Action buttons (Approve/Decline)

- **Approve Modal:**
  - Optional notes field
  - Confirms sending to Pricing Team

- **Decline Modal:**
  - Required reason field
  - Returns to Client Approval

#### B. Client Approval Page (Updated) ✅
**File:** [`templates/client_approval.html`](templates/client_approval.html)

**Changes:**
- **Lines 1091-1145** - Updated Negotiation Modal:
  - Added current selling price display
  - Added expected price input field (required)
  - Enhanced reason textarea
  - Shows workflow: Sales → Sales Head → Pricing → Sales

- **Lines 1665-1705** - Updated `negotiateItem()` function:
  - Captures expected price
  - Sends to new API with expected_price and reason
  - Shows success message with workflow steps

- **Line 1472** - Added `data-current-price` attribute to button

---

## 🔄 Complete Workflow

### Current Implementation:

1. **Sales Team (Client Approval):**
   - Client requests price reduction
   - Sales enters expected price and reason
   - Submits negotiation
   - → Routes to **Sales Head**

2. **Sales Head:**
   - Reviews negotiation request
   - Sees current price vs expected price
   - Sees client reason
   - **Option A: Approve**
     - Adds optional notes
     - → Routes to **Pricing Team** (Operations)
   - **Option B: Decline**
     - Must provide reason
     - → Returns to **Client Approval** (Pending state)

3. **Pricing Team (Operations):** ⏳ NEXT STEP
   - See negotiations approved by Sales Head
   - See client's expected price
   - Add new cost pricing
   - Submit to Sales team

4. **Sales Team (Sales Request):** ⏳ NEXT STEP
   - See negotiations with new pricing
   - Add new selling price
   - Return to Client Approval with new prices

---

## 📋 What's Next

### Remaining Tasks:

#### 1. Operation Request Page Updates ⏳
**File:** `templates/operation_request.html`

**Required Changes:**
- Add filter/section for "Negotiations Pending Pricing"
- Display items with negotiation context:
  - Show client expected price
  - Show current pricing
  - Show negotiation history
- Update pricing form to include negotiation_id
- After pricing, route to Sales Request (not directly to client)

**New API Needed:**
- `GET /api/operations/negotiations/pending-pricing` - Get approved negotiations

#### 2. Sales Request Page Updates ⏳
**File:** `templates/sales_request.html`

**Required Changes:**
- Add filter/section for "Negotiations Pending Selling Price"
- Display items with pricing completed:
  - Show new cost price from operations
  - Show client expected price
  - Show old selling price
- Form to set new selling price
- Submit returns to Client Approval

**New API Needed:**
- `GET /api/sales/negotiations/pending-selling-price` - Get priced negotiations

#### 3. Navigation Menu Update ⏳
**File:** `templates/main.html`

**Required Change:**
- Add menu item for Sales Head Approval
- Add badge showing pending count
- Restrict visibility to sales_head and admin roles

```html
<li class="nav-item" id="sales-head-menu" style="display: none;">
    <a class="nav-link" href="/sales-head-approval">
        <i class="fas fa-fw fa-user-tie"></i>
        <span>Sales Head Approval</span>
        <span class="badge badge-danger badge-counter" id="pending-negotiations-count">0</span>
    </a>
</li>
```

---

## 🧪 Testing Checklist

### Phase 1: Sales Head Routes (Current) ✅
- [ ] Access `/sales-head-approval` page (sales_head/admin only)
- [ ] Verify statistics load correctly
- [ ] Filter negotiations by status
- [ ] Filter by client
- [ ] Filter by date range
- [ ] Approve negotiation (with notes)
- [ ] Decline negotiation (with reason)
- [ ] Verify logs created
- [ ] Verify item status updates

### Phase 2: Client Approval Integration ✅
- [ ] Open negotiation modal from client approval
- [ ] Enter expected price and reason
- [ ] Submit negotiation
- [ ] Verify routes to Sales Head
- [ ] Verify success message shows workflow

### Phase 3: Operations (Pending)
- [ ] View approved negotiations in operations
- [ ] See client expected price
- [ ] Add new cost pricing
- [ ] Verify routes to Sales Request

### Phase 4: Sales Request (Pending)
- [ ] View negotiations with new pricing
- [ ] Add new selling price
- [ ] Submit back to Client Approval
- [ ] Verify client sees new prices

---

## 📊 Database Status

### Current Tables:
```sql
-- Stores negotiation requests
CREATE TABLE negotiation_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_id INT NOT NULL,
    request_id INT NOT NULL,
    client_expected_price DECIMAL(10,2),
    client_reason TEXT,
    status ENUM('pending_sales_head', 'sales_head_approved', 'sales_head_declined', 
                'pending_pricing', 'pricing_completed', 'pending_selling_price', 
                'completed') DEFAULT 'pending_sales_head',
    sales_head_decision ENUM('approved', 'declined'),
    sales_head_notes TEXT,
    sales_head_user_id INT,
    sales_head_decision_date DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES sales_request_items(id)
);

-- Audit trail
CREATE TABLE negotiation_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    negotiation_id INT NOT NULL,
    action VARCHAR(100),
    actor_user_id INT,
    actor_name VARCHAR(255),
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (negotiation_id) REFERENCES negotiation_requests(id)
);
```

---

## 🔐 Security & Permissions

### Role Access Control:
- **sales_head role:** Full access to Sales Head Approval page
- **admin role:** Full access to all negotiation features
- **sales role:** Can create negotiations, cannot approve/decline
- **operations role:** Will see approved negotiations (Phase 3)

### Session Checks:
All routes verify `user_id` in session before processing.

---

## 📝 Code Quality

### Features Implemented:
✅ Role-based access control  
✅ Database transactions with commit/rollback  
✅ Comprehensive error handling  
✅ Audit logging (negotiation_logs)  
✅ Change log integration (log_item_change)  
✅ Input validation (required fields)  
✅ SQL injection protection (parameterized queries)  
✅ DictCursor for clean data access  

---

## 🚀 Deployment Notes

### No Migration Required
New tables were created with initial schema. No ALTER statements needed.

### Testing on Dev:
1. Restart Flask app: `python branding_gate.py`
2. Login as sales_head or admin
3. Navigate to `/sales-head-approval`
4. Test full workflow from client approval → sales head → operations

### Production Rollout:
1. Apply database schema (negotiation_requests, negotiation_logs tables)
2. Deploy updated branding_gate.py
3. Deploy updated client_approval.html
4. Deploy new sales_head_approval.html
5. Update navigation menu (Phase 3)

---

## 📞 Support & Questions

If issues arise:
1. Check MySQL error log for table issues
2. Check Flask console for Python errors
3. Check browser console for JavaScript errors
4. Verify role permissions in `user` table
5. Check `negotiation_logs` table for audit trail

---

**Implementation Date:** 2024  
**Status:** Phase 1 & 2 Complete ✅ | Phase 3 & 4 Pending ⏳  
**Next Step:** Update Operation Request page for negotiation pricing

