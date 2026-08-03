-- =====================================================
-- ENTITY-BASED INVENTORY REVAMP MIGRATION
-- Run Date: January 2026
-- Purpose: Add Entity isolation to inventory system
-- =====================================================

-- Step 1: Create entities table
CREATE TABLE IF NOT EXISTS entities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    entity_name VARCHAR(255) NOT NULL UNIQUE,
    entity_code VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    address TEXT,
    contact_person VARCHAR(255),
    contact_phone VARCHAR(50),
    contact_email VARCHAR(255),
    logo_url VARCHAR(500),
    status ENUM('active', 'inactive') DEFAULT 'active',
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_entity_status (status),
    INDEX idx_entity_code (entity_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Step 2: Add entity_id to inventory_items (allow NULL initially for migration)
ALTER TABLE inventory_items 
ADD COLUMN entity_id INT NULL AFTER id,
ADD INDEX idx_inventory_entity (entity_id);

-- Step 3: Add foreign key constraint (after adding entity_id)
-- Note: Run this AFTER inserting at least one entity
-- ALTER TABLE inventory_items 
-- ADD CONSTRAINT fk_inventory_entity 
-- FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE RESTRICT;

-- Step 4: Remove sales request related columns from inventory_items
-- First, backup the data if needed
-- CREATE TABLE inventory_items_backup AS SELECT * FROM inventory_items;

-- Remove sales request columns (optional - can keep for historical reference)
-- ALTER TABLE inventory_items 
-- DROP COLUMN IF EXISTS source_type,
-- DROP COLUMN IF EXISTS source_id,
-- DROP COLUMN IF EXISTS sales_request_item_id;

-- Step 5: Remove the foreign key to sales_request_items if exists
-- Check for foreign keys first:
-- SHOW CREATE TABLE inventory_items;

-- Step 6: Create a view for entity inventory statistics
CREATE OR REPLACE VIEW v_entity_inventory_stats AS
SELECT 
    e.id AS entity_id,
    e.entity_name,
    e.entity_code,
    COUNT(DISTINCT i.id) AS total_items,
    SUM(i.quantity_in_stock) AS total_stock,
    SUM(i.quantity_in_stock * i.average_cost) AS total_inventory_value,
    SUM(CASE WHEN i.quantity_in_stock <= i.minimum_stock_level THEN 1 ELSE 0 END) AS low_stock_items,
    SUM(CASE WHEN i.quantity_in_stock = 0 THEN 1 ELSE 0 END) AS out_of_stock_items
FROM entities e
LEFT JOIN inventory_items i ON e.id = i.entity_id AND i.is_credit_item = 0
WHERE e.status = 'active'
GROUP BY e.id, e.entity_name, e.entity_code;

-- Step 7: Create a view for credit inventory (entity-independent)
CREATE OR REPLACE VIEW v_credit_inventory_stats AS
SELECT 
    COUNT(DISTINCT i.id) AS total_credit_items,
    SUM(i.quantity_in_stock) AS total_credit_stock,
    SUM(c.quantity_remaining * c.agreed_cost_per_item) AS total_credit_value,
    SUM(c.amount_due) AS total_amount_due,
    COUNT(DISTINCT c.supplier_id) AS supplier_count
FROM inventory_items i
JOIN inventory_credit_items c ON i.id = c.item_id
WHERE i.is_credit_item = 1 AND i.status = 'active';

-- Step 8: Insert a default entity (optional)
-- INSERT INTO entities (entity_name, entity_code, description, created_by)
-- VALUES ('Main Warehouse', 'MAIN-WH', 'Primary warehouse for inventory', 'system');

-- Step 9: Update existing inventory items to belong to default entity (if any exist)
-- UPDATE inventory_items SET entity_id = 1 WHERE entity_id IS NULL AND is_credit_item = 0;

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- Check entities table
-- SELECT * FROM entities;

-- Check inventory items by entity
-- SELECT entity_id, COUNT(*) as item_count FROM inventory_items GROUP BY entity_id;

-- Check entity inventory stats
-- SELECT * FROM v_entity_inventory_stats;

-- Check credit inventory stats
-- SELECT * FROM v_credit_inventory_stats;
