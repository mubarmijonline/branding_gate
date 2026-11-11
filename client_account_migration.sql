-- Every client its own account under 1103 العملاء (Ahmed, 2026-11-11):
-- 11031, 11032, ... in the order the clients were added. A code once given
-- is kept; new clients are numbered by assign_client_accounts().
ALTER TABLE client ADD COLUMN account_code VARCHAR(12) NULL AFTER id,
    ADD UNIQUE KEY uq_client_account_code (account_code);
UPDATE client c
JOIN (SELECT id, ROW_NUMBER() OVER (ORDER BY id) AS n FROM client) x ON x.id = c.id
SET c.account_code = CONCAT('1103', x.n);
