-- Receipts and documents attached to a My Expenses line.
--
-- Files live under private_uploads/expenses/<expense_id>/, outside the
-- nginx-served uploads/ tree, and are read only through
-- /api/expense-attachments/<id>, which checks who is asking.
--
-- One-shot. Re-running fails on the existing table, which is safe.

CREATE TABLE expense_attachments (
    id INT NOT NULL AUTO_INCREMENT,
    expense_id INT NOT NULL,
    stored_path VARCHAR(500) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(100) DEFAULT NULL,
    file_size INT DEFAULT NULL,
    uploaded_by INT DEFAULT NULL,
    uploaded_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_expense_attachments_expense (expense_id),
    CONSTRAINT fk_expense_attachments_expense FOREIGN KEY (expense_id)
        REFERENCES user_expense_tracking (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
