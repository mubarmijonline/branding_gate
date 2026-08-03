# Sales Head Approval - Quick Test Guide

## Prerequisites
1. Database tables created (negotiation_requests, negotiation_logs)
2. Flask app restarted
3. User with 'sales_head' or 'admin' role

---

## Test Scenario 1: Complete Workflow

### Step 1: Create Negotiation (Sales Team)
1. Login as **sales** user
2. Go to **Client Approval** page
3. Find an item with status "Pending Client Approval"
4. Click **"Negotiate Price"** button
5. Fill in modal:
   - **Expected Price:** 450.00 (lower than current)
   - **Reason:** "Client budget constraint for Q4"
6. Click **"Submit Negotiation"**
7. ✅ Should see: "Negotiation submitted to Sales Head for review"

**Verify:**
```sql
SELECT * FROM negotiation_requests ORDER BY id DESC LIMIT 1;
SELECT * FROM negotiation_logs WHERE negotiation_id = <last_id>;
```

### Step 2: Review as Sales Head
1. Logout and login as **sales_head** or **admin**
2. Go to `/sales-head-approval`
3. ✅ Should see:
   - Dashboard with statistics (1 pending)
   - Negotiation card with item details
   - Current price vs Expected price
   - Client reason displayed

### Step 3A: Approve Negotiation
1. Click **"Approve"** button on negotiation card
2. Modal opens - add notes (optional): "Approved for strategic client"
3. Click **"Approve Negotiation"**
4. ✅ Should see: "Negotiation approved and sent to Pricing Team"
5. Card disappears from "Pending" view
6. Switch filter to "Approved" - should see it there

**Verify:**
```sql
-- Check status changed
SELECT status, sales_head_decision, sales_head_notes 
FROM negotiation_requests 
WHERE id = <negotiation_id>;

-- Check log created
SELECT * FROM negotiation_logs 
WHERE negotiation_id = <negotiation_id> 
ORDER BY created_at DESC;

-- Check item status
SELECT approval_status, negotiation_status, client_feedback 
FROM sales_request_items 
WHERE id = <item_id>;
```

**Expected Results:**
- `negotiation_requests.status` = 'pending_pricing'
- `negotiation_requests.sales_head_decision` = 'approved'
- `negotiation_logs` has new entry with action = 'sales_head_approved'
- `sales_request_items.negotiation_status` = 'pending_negotiation'

### Step 3B: Decline Negotiation (Alternative)
1. Click **"Decline"** button instead
2. Modal opens - add reason (required): "Price too low, cannot meet margin requirements"
3. Click **"Decline Negotiation"**
4. ✅ Should see: "Negotiation declined and returned to Pending Client Approval"

**Verify:**
```sql
SELECT status, sales_head_decision, sales_head_notes 
FROM negotiation_requests 
WHERE id = <negotiation_id>;
```

**Expected Results:**
- `negotiation_requests.status` = 'sales_head_declined'
- `negotiation_requests.sales_head_decision` = 'declined'
- `sales_request_items.approval_status` = 'pending' (back to client approval)
- `sales_request_items.negotiation_status` = 'none'

---

## Test Scenario 2: Filters & Search

### Filter by Status
1. Go to Sales Head Approval page
2. Click **"Pending"** filter → Shows only pending_sales_head
3. Click **"Approved"** → Shows only approved negotiations
4. Click **"Declined"** → Shows only declined negotiations
5. Click **"All"** → Shows all negotiations

### Filter by Client
1. Select client from dropdown
2. ✅ Should filter negotiations for that client only

### Filter by Date Range
1. Select **"Today"** → Shows negotiations created today
2. Select **"This Week"** → Shows last 7 days
3. Select **"This Month"** → Shows last 30 days
4. Select **"All Time"** → Shows everything

### Search
1. Type item name in search box
2. ✅ Should filter cards in real-time

---

## Test Scenario 3: Statistics Dashboard

### Setup Multiple Negotiations
1. Create 3-5 negotiations from Client Approval page
2. Approve 2 of them
3. Decline 1 of them
4. Leave 2 pending

### Check Dashboard
1. Go to Sales Head Approval
2. ✅ Verify statistics cards:
   - **Pending:** Should show count of pending negotiations
   - **Approved Today:** Should show count approved today
   - **Declined Today:** Should show count declined today
   - **Potential Savings:** Should show sum of (current_price - expected_price) * quantity

**Verify Calculation:**
```sql
-- Manual calculation
SELECT 
    SUM((sri.sell_per_item - nr.client_expected_price) * sri.qty) as potential_savings
FROM negotiation_requests nr
INNER JOIN sales_request_items sri ON nr.item_id = sri.id
WHERE nr.status = 'pending_sales_head';
```

---

## Test Scenario 4: Permission Checks

### Test Access Control
1. Login as **sales** user (not sales_head)
2. Try to access `/sales-head-approval`
3. ✅ Should be redirected or see "Access Denied"

### Test API Access
1. Login as **sales** user
2. Open browser console
3. Try: `fetch('/api/sales-head/negotiations').then(r => r.json()).then(console.log)`
4. ✅ Should return 401 or 403 error

---

## Test Scenario 5: Error Handling

### Try Double Approval
1. Approve a negotiation
2. Get the negotiation_id from database
3. Try to approve it again via API:
```javascript
fetch('/api/sales-head/negotiations/123/approve', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({notes: 'test'})
}).then(r => r.json()).then(console.log);
```
4. ✅ Should return error: "Negotiation already processed"

### Missing Required Fields
1. Try to decline without reason:
```javascript
fetch('/api/sales-head/negotiations/123/decline', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({reason: ''})
}).then(r => r.json()).then(console.log);
```
2. ✅ Should return error: "Reason is required"

---

## Test Scenario 6: Database Consistency

### Check Logs Created
After each approval/decline:
```sql
SELECT 
    nl.action,
    nl.actor_name,
    nl.notes,
    nl.created_at,
    nr.status
FROM negotiation_logs nl
INNER JOIN negotiation_requests nr ON nl.negotiation_id = nr.id
WHERE nl.negotiation_id = <negotiation_id>
ORDER BY nl.created_at;
```

✅ Should see:
1. Initial log: action='negotiation_created'
2. Decision log: action='sales_head_approved' OR 'sales_head_declined'

### Check Main Change Log
```sql
SELECT * FROM sales_request_item_changes 
WHERE item_id = <item_id> 
AND action_type IN ('CLIENT_NEGOTIATION', 'SALES_HEAD_APPROVED', 'SALES_HEAD_DECLINED')
ORDER BY created_at DESC;
```

---

## Expected Issues & Solutions

### Issue: Page doesn't load
**Solution:** Check Flask console for errors. Verify role_required decorator works.

### Issue: No negotiations showing
**Solution:** 
- Check database: `SELECT * FROM negotiation_requests;`
- Check filters aren't too restrictive
- Check user has correct role

### Issue: Statistics show 0
**Solution:**
- Create some negotiations first
- Check date filters
- Verify SQL queries in get_sales_head_statistics route

### Issue: Approve/Decline doesn't work
**Solution:**
- Open browser console for JavaScript errors
- Check Flask logs for backend errors
- Verify negotiation_id is correct
- Check user session

---

## Quick SQL Queries for Testing

```sql
-- View all negotiations
SELECT 
    nr.id,
    nr.status,
    nr.client_expected_price,
    nr.sales_head_decision,
    sri.name as item_name,
    c.client_name
FROM negotiation_requests nr
INNER JOIN sales_request_items sri ON nr.item_id = sri.id
INNER JOIN sales_request sr ON sri.request_id = sr.id
LEFT JOIN client c ON sr.client_id = c.id
ORDER BY nr.created_at DESC;

-- View negotiation with full history
SELECT 
    nl.*,
    nr.status as current_status
FROM negotiation_logs nl
INNER JOIN negotiation_requests nr ON nl.negotiation_id = nr.id
WHERE nl.negotiation_id = <ID>
ORDER BY nl.created_at;

-- View pending negotiations for sales head
SELECT * FROM negotiation_requests 
WHERE status = 'pending_sales_head'
ORDER BY created_at DESC;

-- Reset a negotiation for re-testing
UPDATE negotiation_requests 
SET status = 'pending_sales_head',
    sales_head_decision = NULL,
    sales_head_notes = NULL,
    sales_head_user_id = NULL,
    sales_head_decision_date = NULL
WHERE id = <ID>;
```

---

## Success Criteria

✅ **Phase 1 Complete When:**
- Sales Head page loads without errors
- Statistics display correctly
- Negotiations display with all details
- Filters work correctly
- Approve flow works and updates database
- Decline flow works and returns to client approval
- Logs are created for all actions
- Permissions block unauthorized users

🎯 **Ready for Phase 3** (Operations/Pricing integration)

