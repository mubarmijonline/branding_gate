-- Extra permissions granted from the People & Access screen, on top of the
-- role grants that seed_rbac.py regenerates from rbac.py. Seeding never
-- touches this table.
CREATE TABLE IF NOT EXISTS permission_grant (
  id INT NOT NULL AUTO_INCREMENT,
  target_type ENUM('role','department','team','user') NOT NULL,
  target_id INT NOT NULL,
  permission_code VARCHAR(64) NOT NULL,
  scope ENUM('own','team','department','all') NOT NULL DEFAULT 'all',
  granted_by INT NULL,
  granted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_permission_grant (target_type, target_id, permission_code),
  KEY idx_permission_grant_code (permission_code),
  CONSTRAINT fk_permission_grant_permission FOREIGN KEY (permission_code)
    REFERENCES permission (code) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
