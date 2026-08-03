-- RBAC revamp, phase 7: retire the legacy role table.
--
-- Nothing in the application reads or writes it any more; authorization runs
-- entirely off rbac_role / role_permission and user.rbac_role_id. Renaming
-- rather than dropping keeps the rows recoverable: the rollback is the
-- opposite rename.
--
--   Rollback:  RENAME TABLE role_legacy TO role;
RENAME TABLE role TO role_legacy;
