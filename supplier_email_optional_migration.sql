-- A supplier without an email address.
--
-- Plenty of suppliers are reached on a phone number and nothing else, and the
-- form refused to save one without an email -- so the address being typed in
-- was frequently a placeholder, which is worse than an empty column.
--
-- The column was NOT NULL with no default, so "no email" could only be stored
-- as an empty string. It is nullable now: absent means absent.
--
-- One-shot. DDL commits implicitly in MySQL, so this file is deliberately
-- outside any transaction.

ALTER TABLE supplier
    MODIFY COLUMN email_address VARCHAR(255) NULL
        COMMENT 'Optional: many suppliers are reached by phone only';

-- The placeholders that were typed in only to get past the old rule stay as
-- they are; nothing here guesses which of them were real.
UPDATE supplier SET email_address = NULL WHERE TRIM(email_address) = '';
