-- Stock held under a code inside one item.
--
-- One item ("ميلجا") can hold general stock and stock received under a code
-- (a job, PO or supplier code: "10"). A movement may carry that code; the
-- item's stock per code is the sum of its coded movements, and general is
-- whatever of the total is not under a code.
--
-- One-shot. Re-running fails on the duplicate column, which is safe.

ALTER TABLE inventory_transactions
    ADD COLUMN lot_code VARCHAR(50) NULL DEFAULT NULL AFTER reference_id,
    ADD INDEX idx_inventory_transactions_lot (item_id, lot_code);
