#!/bin/bash

echo "========================================="
echo "CURRENT STATE OF REQUEST 14"
echo "========================================="

mysql -ups -p'Aa@123456' branding_gate << 'EOF'
-- Main request data
SELECT 
    id, 
    title, 
    DATE_FORMAT(start_date, '%Y-%m-%d') as start_date, 
    DATE_FORMAT(end_date, '%Y-%m-%d') as end_date,
    request_type,
    items_count,
    request_data
FROM sales_request 
WHERE id = 14\G

-- Items
SELECT 
    id,
    name,
    qty,
    unit,
    CAST(attributes AS CHAR) as attributes,
    description
FROM sales_request_items
WHERE request_id = 14;

-- Recent change logs (last 5)
SELECT 
    id,
    action_type,
    field_name,
    DATE_FORMAT(action_date, '%Y-%m-%d %H:%i:%s') as action_date,
    action_by,
    LEFT(old_value, 50) as old_value_preview,
    LEFT(new_value, 50) as new_value_preview,
    change_description
FROM sales_request_change_log
WHERE request_id = 14
ORDER BY action_date DESC
LIMIT 5;
EOF

echo ""
echo "========================================="
echo "INSTRUCTIONS:"
echo "========================================="
echo "1. Go to your browser and open the request 14"
echo "2. Make a change (e.g., change item quantity or dimensions)"
echo "3. Save the changes"
echo "4. Check the server terminal for DEBUG output"
echo "5. Run this script again to see what changed"
echo ""
echo "The DEBUG output will show:"
echo "  - DEBUG LOGGING: Comparison of old vs new items"
echo "  - DEBUG DIMENSIONS: Dimension comparisons with exact differences"
echo "  - DEBUG TEMPLATE FIELD: Template field comparisons"
echo ""
