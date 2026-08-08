-- عهدة: the manager's signature, the sales request behind every expense line,
-- and settling what is left.
--
-- One running عهدة per person -- the balance already in user_finance_balances.
-- What this adds is the layer above the requester signing before Finance sees
-- it, the sales request an expense was spent on, and the way money comes back.
--
-- One-shot. Re-running fails on a duplicate column, which is safe. DDL commits
-- implicitly in MySQL, so this file is deliberately outside any transaction and
-- a --dry-run containing it would not be dry.

-- ---------------------------------------------------------------------------
-- 1. A balance request now waits on a manager before it waits on Finance
-- ---------------------------------------------------------------------------

-- 'pending' could not say who was holding it. Two queues, two words.
ALTER TABLE user_balance_transfers
    MODIFY COLUMN status ENUM('pending', 'pending_manager', 'pending_finance',
                              'approved', 'rejected', 'cancelled')
                   NOT NULL DEFAULT 'pending_manager';

-- The same three columns, under the same names, that expense_tracking already
-- uses for its manager step.
ALTER TABLE user_balance_transfers
    ADD COLUMN manager_approved_by INT NULL AFTER requested_by,
    ADD COLUMN manager_approved_at DATETIME NULL AFTER manager_approved_by,
    ADD COLUMN manager_notes TEXT NULL AFTER manager_approved_at,
    -- What was asked for, when a manager corrects it. The amount column always
    -- holds the live figure; this holds what the person originally typed.
    ADD COLUMN original_amount DECIMAL(15, 2) NULL AFTER amount;

ALTER TABLE user_balance_transfers
    ADD CONSTRAINT fk_ubt_manager_approved_by
        FOREIGN KEY (manager_approved_by) REFERENCES user (id);

-- Handing money back is a row on the same table, in the other direction, so it
-- queues and reads like everything else.
ALTER TABLE user_balance_transfers
    MODIFY COLUMN transfer_type ENUM('admin_transfer', 'user_request',
                                     'adjustment', 'settlement') NOT NULL;

-- The payment method a settlement is returned onto, chosen by Finance when it
-- confirms the cash arrived.
ALTER TABLE user_balance_transfers
    ADD COLUMN payment_method_id INT NULL AFTER approved_by;

-- Nothing is mid-flight: every existing row is already approved. The default
-- above governs new rows, and the route decides between pending_manager and
-- pending_finance from the requester's own reporting line.
UPDATE user_balance_transfers SET status = 'pending_finance'
 WHERE status = 'pending';

-- ---------------------------------------------------------------------------
-- 2. Every expense line names the work it was spent on
-- ---------------------------------------------------------------------------

ALTER TABLE expense_tracking_items
    ADD COLUMN sales_request_id INT NULL AFTER tracking_id;

ALTER TABLE expense_tracking_items
    ADD CONSTRAINT fk_expense_item_sales_request
        FOREIGN KEY (sales_request_id) REFERENCES sales_request (id);

CREATE INDEX idx_expense_item_sales_request
    ON expense_tracking_items (sales_request_id);

-- Required from here on, enforced in the route rather than by NOT NULL: the one
-- row already recorded predates the rule and dropping it to satisfy a
-- constraint would be losing a record to tidy a column.

-- What a manager corrected, per line. The header already keeps
-- original_total_amount for the same reason.
ALTER TABLE expense_tracking_items
    ADD COLUMN original_amount DECIMAL(15, 2) NULL AFTER amount;

-- ---------------------------------------------------------------------------
-- 3. The عهدة ledger learns the two new words
-- ---------------------------------------------------------------------------

ALTER TABLE user_balance_history
    MODIFY COLUMN change_type ENUM('transfer_in', 'transfer_out',
                                   'request_approved', 'adjustment', 'expense',
                                   'opening', 'settlement') NOT NULL;
