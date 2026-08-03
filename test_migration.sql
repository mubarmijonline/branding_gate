-- Test SQL Migration File
-- Created to test if .sql files are properly written to disk

USE branding_gate;

-- Simple test query
SELECT 'SQL file creation test' as test_status;

-- Show current database
SELECT DATABASE() as current_database;

-- Count inventory items
SELECT COUNT(*) as total_items FROM inventory_items;
