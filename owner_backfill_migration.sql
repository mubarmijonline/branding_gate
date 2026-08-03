-- RBAC revamp, phase 6: populate the real owner columns.
--
-- Row-level scope needs an integer owner. The legacy free-text columns stay
-- for reference and stop being read from this point on:
--   sales_request.created_by  holds user.username (often the mobile number)
--   client.added_by           holds user.username, or the literal 'admin'
--   finance_transactions.added_by holds user.name
--
-- Idempotent: every statement only fills rows that are still NULL, so this can
-- be re-run safely and can be applied before the code that reads the columns.

-- Sales requests: resolve by username, then fall back to the recovery account.
UPDATE sales_request sr
  JOIN user u ON u.username = sr.created_by
   SET sr.owner_user_id = u.id
 WHERE sr.owner_user_id IS NULL;

UPDATE sales_request
   SET owner_user_id = 1
 WHERE owner_user_id IS NULL;

-- Clients: same, but 'admin' and other legacy literals match no user row.
UPDATE client c
  JOIN user u ON u.username = c.added_by
   SET c.owner_user_id = u.id
 WHERE c.owner_user_id IS NULL;

UPDATE client
   SET owner_user_id = 1
 WHERE owner_user_id IS NULL;

-- Items inherit their request's owner. submitted_by already exists as an int
-- column and was never populated, so it is reused rather than adding a third
-- ownership convention.
--
-- The trigger update_request_approval_stats_after_item_update writes back to
-- sales_request, so MySQL refuses an UPDATE that also joins that table
-- (error 1442). Copy the mapping out first, then join against the copy.
CREATE TEMPORARY TABLE _sr_owner_map AS
    SELECT id, owner_user_id FROM sales_request;

UPDATE sales_request_items i
  JOIN _sr_owner_map o ON o.id = i.request_id
   SET i.submitted_by = o.owner_user_id
 WHERE i.submitted_by IS NULL;

DROP TEMPORARY TABLE _sr_owner_map;

-- Finance transactions already carry added_by_user_id; fill any gaps by name.
UPDATE finance_transactions ft
  JOIN user u ON u.name = ft.added_by
   SET ft.added_by_user_id = u.id
 WHERE ft.added_by_user_id IS NULL;

UPDATE finance_transactions
   SET added_by_user_id = 1
 WHERE added_by_user_id IS NULL;
