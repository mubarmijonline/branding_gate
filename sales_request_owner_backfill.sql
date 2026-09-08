-- Requests written before claim_sales_request() existed carry no owner, and
-- every list is scoped on sr.owner_user_id -- so they were invisible to
-- everyone but an 'all' scope. The creator's username is the only record of
-- who raised them; match it back to the user row.
UPDATE sales_request sr
  JOIN user u ON u.username = sr.created_by
   SET sr.owner_user_id = u.id
 WHERE sr.owner_user_id IS NULL;
