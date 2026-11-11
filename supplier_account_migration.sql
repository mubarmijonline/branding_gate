-- Every supplier its own account under 2101 الموردين (Ahmed, 2026-11-11):
-- 21011, 21012, ... in the order the suppliers were added. A code once given
-- is kept; new suppliers are numbered by assign_supplier_accounts().
ALTER TABLE supplier ADD COLUMN account_code VARCHAR(12) NULL AFTER id,
    ADD UNIQUE KEY uq_supplier_account_code (account_code);
UPDATE supplier s
JOIN (SELECT id, ROW_NUMBER() OVER (ORDER BY id) AS n FROM supplier) x ON x.id = s.id
SET s.account_code = CONCAT('2101', x.n);
