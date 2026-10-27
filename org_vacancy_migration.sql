-- Positions nobody holds yet, drawn on the org chart as vacant boxes.
-- A person under a vacancy keeps manager_id = the nearest real person above
-- it (approval chains need a person), and reports_to_vacancy_id places them on
-- the chart.
CREATE TABLE IF NOT EXISTS org_vacancy (
  id INT NOT NULL AUTO_INCREMENT,
  rbac_role_id INT NOT NULL,
  department_id INT NULL,
  title VARCHAR(120) NOT NULL,
  parent_user_id INT NULL,
  parent_vacancy_id INT NULL,
  created_by INT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_org_vacancy_role FOREIGN KEY (rbac_role_id) REFERENCES rbac_role (id),
  CONSTRAINT fk_org_vacancy_department FOREIGN KEY (department_id) REFERENCES department (id),
  CONSTRAINT fk_org_vacancy_parent_user FOREIGN KEY (parent_user_id) REFERENCES user (id) ON DELETE SET NULL,
  CONSTRAINT fk_org_vacancy_parent FOREIGN KEY (parent_vacancy_id) REFERENCES org_vacancy (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE user ADD COLUMN reports_to_vacancy_id INT NULL,
  ADD CONSTRAINT fk_user_reports_to_vacancy FOREIGN KEY (reports_to_vacancy_id)
    REFERENCES org_vacancy (id) ON DELETE SET NULL;
