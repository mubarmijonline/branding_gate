-- Send part of a request to Pricing (David, 2026-10-29). The hand-off moves
-- from the request to the item: Operation can send three costed items of ten
-- while the other seven are still being costed. sales_request.pricing_handoff_at
-- stays as "the first time anything of it reached Pricing", which is what
-- puts the request on the Pricing desk.
ALTER TABLE sales_request_items
  ADD COLUMN pricing_sent_at DATETIME NULL,
  ADD COLUMN pricing_sent_by INT NULL;

-- Everything already handed over stays handed over. Through a temporary
-- table: the item triggers write sales_request, so the UPDATE may not read it.
CREATE TEMPORARY TABLE handed_over AS
  SELECT id, pricing_handoff_at, pricing_handoff_by FROM sales_request WHERE pricing_handoff_at IS NOT NULL;
UPDATE sales_request_items i
JOIN handed_over h ON h.id = i.request_id
SET i.pricing_sent_at = h.pricing_handoff_at, i.pricing_sent_by = h.pricing_handoff_by
WHERE i.pricing_sent_at IS NULL;
DROP TEMPORARY TABLE handed_over;
