-- Disabling an account without removing the person.
--
-- The seeded placeholders hold real positions in the reporting line: people
-- report to them, scopes are computed from them, and deleting them would move
-- everybody underneath. So they stay in the tree and lose only the ability to
-- log in, which is the one thing about them that is a liability -- their seeded
-- passwords are written down in backups/seeded_credentials.txt.
--
-- One-shot. Re-running fails on the duplicate column, which is safe. DDL
-- commits implicitly in MySQL, so this file is outside any transaction.

ALTER TABLE user
    ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1 AFTER is_pricing;

-- Everybody who exists today keeps their login; the placeholders are switched
-- off by the script that knows which ones they are, not by this file.
CREATE INDEX idx_user_is_active ON user (is_active);
