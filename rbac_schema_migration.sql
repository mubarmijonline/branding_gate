-- RBAC revamp, phase 2: additive schema only.
--
-- Creates the department / role / permission model and the ownership and
-- hierarchy columns the scope predicates will need. Nothing here is read by
-- the application yet, so it can be applied to a running instance.
--
-- One-shot. Re-running fails loudly on the ADD COLUMN statements ("Duplicate
-- column name"), which is safe: no data is written or dropped.
--
-- The legacy `role` table and its team_flag overload are left untouched and
-- keep serving role_required until the cutover.

-- ---------------------------------------------------------------------------
-- Departments
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS department (
    id   INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(32)  NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    added_date    DATETIME DEFAULT CURRENT_TIMESTAMP,
    modified_date DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Roles. `level` orders the hierarchy: 0 executive, 1 head/manager,
-- 2 team leader, 3 member. department_id is NULL for company-wide roles
-- (admin, assistant).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rbac_role (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    code          VARCHAR(48)  NOT NULL UNIQUE,
    name          VARCHAR(100) NOT NULL,
    department_id INT NULL,
    level         TINYINT NOT NULL,
    added_date    DATETIME DEFAULT CURRENT_TIMESTAMP,
    modified_date DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_rbac_role_department FOREIGN KEY (department_id) REFERENCES department(id),
    KEY idx_rbac_role_level (level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Permission vocabulary. Seeded from rbac.PERMISSIONS in phase 3.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS permission (
    code        VARCHAR(64) PRIMARY KEY,
    description VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Grants. Scope lives on the grant, not the permission, so the same role can
-- hold team scope on one resource and own scope on another.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS role_permission (
    role_id         INT NOT NULL,
    permission_code VARCHAR(64) NOT NULL,
    scope           ENUM('own','team','department','all') NOT NULL DEFAULT 'own',
    PRIMARY KEY (role_id, permission_code),
    CONSTRAINT fk_role_permission_role FOREIGN KEY (role_id) REFERENCES rbac_role(id) ON DELETE CASCADE,
    CONSTRAINT fk_role_permission_permission FOREIGN KEY (permission_code) REFERENCES permission(code) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- User hierarchy: department, single role, and reporting line.
-- manager_id is what team scope resolves through.
-- ---------------------------------------------------------------------------
ALTER TABLE user
    ADD COLUMN department_id INT NULL AFTER team_id,
    ADD COLUMN rbac_role_id  INT NULL AFTER department_id,
    ADD COLUMN manager_id    INT NULL AFTER rbac_role_id,
    ADD KEY idx_user_department (department_id),
    ADD KEY idx_user_rbac_role (rbac_role_id),
    ADD KEY idx_user_manager (manager_id),
    ADD CONSTRAINT fk_user_department FOREIGN KEY (department_id) REFERENCES department(id),
    ADD CONSTRAINT fk_user_rbac_role  FOREIGN KEY (rbac_role_id)  REFERENCES rbac_role(id),
    ADD CONSTRAINT fk_user_manager    FOREIGN KEY (manager_id)    REFERENCES user(id);

-- team.department_name stays for reference; department_id becomes the real link.
ALTER TABLE team
    ADD COLUMN department_id INT NULL AFTER department_name,
    ADD KEY idx_team_department (department_id),
    ADD CONSTRAINT fk_team_department FOREIGN KEY (department_id) REFERENCES department(id);

-- ---------------------------------------------------------------------------
-- Record ownership as a real user id. The existing free-text created_by /
-- added_by columns are kept for reference and stop being read at phase 6.
-- ---------------------------------------------------------------------------
ALTER TABLE sales_request
    ADD COLUMN owner_user_id INT NULL AFTER created_by,
    ADD KEY idx_sales_request_owner (owner_user_id),
    ADD CONSTRAINT fk_sales_request_owner FOREIGN KEY (owner_user_id) REFERENCES user(id);

ALTER TABLE client
    ADD COLUMN owner_user_id INT NULL AFTER added_by,
    ADD KEY idx_client_owner (owner_user_id),
    ADD CONSTRAINT fk_client_owner FOREIGN KEY (owner_user_id) REFERENCES user(id);
