-- Payment methods are either cash (a safe/box) or a bank account. A bank
-- method must carry its bank name and account number; the API enforces that.
--
-- One-shot. Re-running fails on the duplicate column, which is safe.

ALTER TABLE payment_methods
    ADD COLUMN method_type ENUM('cash', 'bank') NOT NULL DEFAULT 'cash' AFTER method_code;

-- Rows that already name a bank are bank accounts.
UPDATE payment_methods SET method_type = 'bank'
 WHERE COALESCE(bank_name, '') <> '' OR COALESCE(account_number, '') <> '';
