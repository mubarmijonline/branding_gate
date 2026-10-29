-- Re-costing after a change (Gamal, 2026-10-30). Sales may change a costed
-- item only by asking for it to be costed again: the change is applied, the
-- cost and price are cleared, and these mark the item until Operations costs
-- it again.
ALTER TABLE sales_request_items
  ADD COLUMN recost_requested_at DATETIME NULL,
  ADD COLUMN recost_requested_by INT NULL,
  ADD COLUMN recost_note VARCHAR(1000) NULL;
