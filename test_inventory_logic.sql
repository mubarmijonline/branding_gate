-- ================================================================
-- TEST INVENTORY UNIQUENESS & SMART LOGIC
-- ================================================================
USE branding_gate;

SELECT '=== TEST 1: Verify Unique Constraint ===' as test;

-- Try to insert duplicate item (should fail on second insert)
INSERT INTO inventory_items 
    (item_code, item_name, unit_of_measure, width, height, depth, item_type, status)
VALUES 
    ('TEST-001', 'Test Unique Item', 'pcs', 1.00, 2.00, 3.00, 'simple', 'active');

-- This should fail with duplicate key error on idx_unique_item
INSERT IGNORE INTO inventory_items 
    (item_code, item_name, unit_of_measure, width, height, depth, item_type, status)
VALUES 
    ('TEST-002', 'Test Unique Item', 'pcs', 1.00, 2.00, 3.00, 'simple', 'active');

-- Check result
SELECT 
    CASE 
        WHEN COUNT(*) = 1 THEN '✓ Unique constraint working - only 1 item created'
        ELSE '✗ ERROR - duplicate items created!'
    END as result
FROM inventory_items 
WHERE item_name = 'Test Unique Item'
  AND unit_of_measure = 'pcs'
  AND width = 1.00 AND height = 2.00 AND depth = 3.00;

-- Clean up
DELETE FROM inventory_items WHERE item_code LIKE 'TEST-%';


SELECT '=== TEST 2: Verify Transaction Creation ===' as test;

-- Check that all items with stock have transactions
SELECT 
    i.id,
    i.item_code,
    i.item_name,
    i.quantity_in_stock,
    COUNT(t.id) as transaction_count,
    COALESCE(SUM(CASE 
        WHEN t.transaction_type IN ('purchase', 'credit_in', 'adjustment') THEN t.quantity
        WHEN t.transaction_type IN ('sale', 'credit_out') THEN -t.quantity
        ELSE 0
    END), 0) as calculated_stock,
    CASE 
        WHEN i.quantity_in_stock = COALESCE(SUM(CASE 
            WHEN t.transaction_type IN ('purchase', 'credit_in', 'adjustment') THEN t.quantity
            WHEN t.transaction_type IN ('sale', 'credit_out') THEN -t.quantity
            ELSE 0
        END), 0) THEN '✓ Match'
        ELSE '✗ Mismatch!'
    END as integrity_check
FROM inventory_items i
LEFT JOIN inventory_transactions t ON i.id = t.item_id
WHERE i.status = 'active'
GROUP BY i.id, i.item_code, i.item_name, i.quantity_in_stock
ORDER BY i.id;


SELECT '=== TEST 3: Credit Items Tracking ===' as test;

-- Show credit items and their stock allocation
SELECT 
    i.item_code,
    i.item_name,
    i.quantity_in_stock as total_stock,
    COALESCE(SUM(c.quantity_remaining), 0) as credit_stock,
    i.quantity_in_stock - COALESCE(SUM(c.quantity_remaining), 0) as owned_stock
FROM inventory_items i
LEFT JOIN inventory_credit_items c ON i.id = c.item_id AND c.status = 'active'
WHERE i.status = 'active'
GROUP BY i.id, i.item_code, i.item_name, i.quantity_in_stock;


SELECT '=== TEST 4: Dimension-Based Uniqueness ===' as test;

-- Show items grouped by name+unit+dimensions
SELECT 
    item_name,
    unit_of_measure,
    COALESCE(width, 0) as width,
    COALESCE(height, 0) as height,
    COALESCE(depth, 0) as depth,
    COUNT(*) as item_count,
    GROUP_CONCAT(item_code) as item_codes,
    SUM(quantity_in_stock) as total_stock
FROM inventory_items
WHERE status = 'active'
GROUP BY item_name, unit_of_measure, COALESCE(width, 0), COALESCE(height, 0), COALESCE(depth, 0)
ORDER BY item_name;


SELECT '=== SUMMARY STATISTICS ===' as test;

SELECT 
    'Total Active Items' as metric,
    COUNT(*) as value
FROM inventory_items
WHERE status = 'active'
UNION ALL
SELECT 
    'Total Stock Units',
    CAST(SUM(quantity_in_stock) as SIGNED)
FROM inventory_items
WHERE status = 'active'
UNION ALL
SELECT 
    'Total Transactions',
    COUNT(*)
FROM inventory_transactions
UNION ALL
SELECT 
    'Active Credit Items',
    COUNT(*)
FROM inventory_credit_items
WHERE status = 'active'
UNION ALL
SELECT 
    'Unique Item Names',
    COUNT(DISTINCT item_name)
FROM inventory_items
WHERE status = 'active';

SELECT '=== ALL TESTS COMPLETE ===' as status;
