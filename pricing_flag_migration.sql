-- Pricing as an account flag.
--
-- Pricing is a responsibility that does not always follow the org chart: a
-- Sales Head or an Operations Manager may own pricing without changing job.
-- The flag grants the pricing permissions on top of whatever the role already
-- gives, so either the role or the flag is enough.
--
-- One-shot. Re-running fails on the duplicate column, which is safe.
ALTER TABLE user
    ADD COLUMN is_pricing TINYINT(1) NOT NULL DEFAULT 0 AFTER rbac_role_id,
    ADD KEY idx_user_is_pricing (is_pricing);
