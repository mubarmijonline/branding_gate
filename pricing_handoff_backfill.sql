-- Run once, right after deploying the Send to Pricing code. A request Pricing
-- could already work on stays with Pricing: every item costed, or any item
-- already priced. A partly costed, unpriced request goes back to Operation
-- until someone sends it.
UPDATE sales_request sr
JOIN (SELECT request_id FROM sales_request_items
      GROUP BY request_id
      HAVING SUM(cost_per_item IS NULL) = 0 OR SUM(sell_per_item > 0) > 0) done
  ON done.request_id = sr.id
SET sr.pricing_handoff_at = NOW()
WHERE sr.pricing_handoff_at IS NULL;
