-- ================================================================
-- INVENTORY UNIQUENESS & TRANSACTION TRACKING MIGRATION
-- ================================================================
USE branding_gate;

-- Step 1: Add unique constraint
-- Drop index if exists (MySQL 5.7 compatible syntax)
SET @sql = IF(
    (SELECT COUNT(*) FROM information_schema.statistics 
     WHERE table_schema = 'branding_gate' 
     AND table_name = 'inventory_items' 
     AND index_name = 'idx_unique_item') > 0,
    'ALTER TABLE inventory_items DROP INDEX idx_unique_item',
    'SELECT "Index does not exist" as msg'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Create unique index
ALTER TABLE inventory_items 
ADD UNIQUE INDEX idx_unique_item (item_name, unit_of_measure, width, height, depth);

SELECT '✓ Unique constraint added' as status;

-- Step 2: Create initial transactions for items with stock
-- Temporarily disable trigger to prevent conflict
DROP TRIGGER IF EXISTS update_inventory_stock_after_transaction;

INSERT INTO inventory_transactions 
    (item_id, transaction_type, quantity, unit_cost, total_cost, 
     transaction_date, notes, performed_by, balance_after)
SELECT 
    i.id, 'purchase', i.quantity_in_stock,
    COALESCE(i.average_cost, 0),
    i.quantity_in_stock * COALESCE(i.average_cost, 0),
    COALESCE(i.created_at, NOW()),
    'Initial inventory - migrated from existing stock',
    COALESCE(i.created_by, 'system'),
    i.quantity_in_stock
FROM inventory_items i
LEFT JOIN inventory_transactions t ON i.id = t.item_id
WHERE i.quantity_in_stock > 0
GROUP BY i.id
HAVING COUNT(t.id) = 0;

-- Recreate the trigger
DELIMITER $$
CREATE TRIGGER update_inventory_stock_after_transaction
BEFORE INSERT ON inventory_transactions
FOR EACH ROW
BEGIN
    DECLARE current_stock DECIMAL(10, 2);
    DECLARE new_stock DECIMAL(10, 2);
    
    SELECT quantity_in_stock INTO current_stock
    FROM inventory_items
    WHERE id = NEW.item_id;
    
    IF NEW.transaction_type IN ('purchase', 'credit_in', 'return', 'adjustment') THEN
        SET new_stock = current_stock + NEW.quantity;
    ELSEIF NEW.transaction_type IN ('sale', 'credit_out', 'transfer') THEN
        SET new_stock = current_stock - NEW.quantity;
    ELSE
        SET new_stock = current_stock;
    END IF;
    
    SET NEW.balance_after = new_stock;
    
    UPDATE inventory_items
    SET quantity_in_stock = new_stock,
        last_purchase_cost = CASE WHEN NEW.transaction_type = 'purchase' THEN NEW.unit_cost ELSE last_purchase_cost END,
        average_cost = CASE 
            WHEN NEW.transaction_type IN ('purchase', 'credit_in') THEN
                ((average_cost * current_stock) + (NEW.unit_cost * NEW.quantity)) / (current_stock + NEW.quantity)
            ELSE average_cost
        END
    WHERE id = NEW.item_id;
    
    IF new_stock <= (SELECT minimum_stock_level FROM inventory_items WHERE id = NEW.item_id) THEN
        INSERT INTO inventory_alerts (item_id, alert_type, alert_message, severity)
        VALUES (NEW.item_id, 'low_stock', 
                CONCAT('Stock level is low: ', new_stock, ' units remaining'), 
                CASE WHEN new_stock = 0 THEN 'critical' ELSE 'high' END)
        ON DUPLICATE KEY UPDATE alert_message = VALUES(alert_message), severity = VALUES(severity);
    END IF;
END$$
DELIMITER ;

SELECT '✓ Initial transactions created' as status;

-- Verification
SELECT '=== VERIFICATION ===' as status;

SELECT 'Unique Index' as test, COUNT(*) as result
FROM information_schema.statistics
WHERE table_schema = 'branding_gate'
  AND table_name = 'inventory_items'
  AND index_name = 'idx_unique_item';

SELECT '=== MIGRATION COMPLETE ===' as status;

-- Show summary of results
SELECT 
    'Summary' as info,
    COUNT(DISTINCT i.id) as total_items,
    SUM(i.quantity_in_stock) as total_stock,
    COUNT(DISTINCT t.id) as total_transactions
FROM inventory_items i
LEFT JOIN inventory_transactions t ON i.id = t.item_id;
