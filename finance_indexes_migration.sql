-- Finance Transactions - Composite Indexes for Big Data Performance
-- Created for optimizing filtering, reporting, and aggregation queries
-- Run: mysql -u ps -p'Aa@123456' branding_gate < finance_indexes_migration.sql

-- Main listing query: WHERE status='approved' ORDER BY transaction_date DESC
CREATE INDEX IF NOT EXISTS idx_status_date ON finance_transactions(status, transaction_date DESC);

-- Reporting aggregations: GROUP BY with SUM(CASE WHEN transaction_type=...)
CREATE INDEX IF NOT EXISTS idx_status_type ON finance_transactions(status, transaction_type);

-- Client report: JOIN on client_id with status filter
CREATE INDEX IF NOT EXISTS idx_status_client_type ON finance_transactions(status, client_id, transaction_type);

-- Supplier report: JOIN on supplier_id with status filter
CREATE INDEX IF NOT EXISTS idx_status_supplier_type ON finance_transactions(status, supplier_id, transaction_type);

-- Payment method report: JOIN on payment_method_id with status filter
CREATE INDEX IF NOT EXISTS idx_status_pm_type ON finance_transactions(status, payment_method_id, transaction_type);

-- Category multi-select filtering
CREATE INDEX IF NOT EXISTS idx_status_cat_subcat ON finance_transactions(status, category_id, subcategory_id);

-- Date-range reports with status + type
CREATE INDEX IF NOT EXISTS idx_date_status_type ON finance_transactions(transaction_date, status, transaction_type);
