-- Send to Pricing (David, 2026-10-28): Pricing sees a request only after
-- Operation hands it over, once every item is costed. A cost changed after
-- that leaves it with Pricing and marks it "cost changed" until re-priced.
ALTER TABLE sales_request
  ADD COLUMN pricing_handoff_at DATETIME NULL,
  ADD COLUMN pricing_handoff_by INT NULL,
  ADD COLUMN cost_changed_at DATETIME NULL,
  ADD KEY idx_sales_request_pricing_handoff (pricing_handoff_at);
