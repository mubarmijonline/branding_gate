-- Design requests (Gamal, 2026-10-28; docs/PRD.md "Design Requests").
-- A request is a header plus items; Design assigns one designer to it, the
-- designer's files are its deliverables, and every step lands in the log.
CREATE TABLE IF NOT EXISTS design_request (
  id INT NOT NULL AUTO_INCREMENT,
  discipline ENUM('2d','3d') NOT NULL DEFAULT '2d',
  company_id INT NULL,
  client_id INT NOT NULL,
  event_date DATE NULL,
  deadline DATE NULL,
  status ENUM('submitted','assigned','in_review','changes','approved','sent_to_operation','cancelled')
         NOT NULL DEFAULT 'submitted',
  created_by INT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  designer_id INT NULL,
  assigned_by INT NULL,
  assigned_at DATETIME NULL,
  submitted_at DATETIME NULL,
  decided_by INT NULL,
  decided_at DATETIME NULL,
  decision_note VARCHAR(1000) NULL,
  sent_by INT NULL,
  sent_at DATETIME NULL,
  PRIMARY KEY (id),
  KEY idx_design_request_status (discipline, status),
  KEY idx_design_request_designer (designer_id),
  CONSTRAINT fk_design_request_client FOREIGN KEY (client_id) REFERENCES client (id),
  CONSTRAINT fk_design_request_company FOREIGN KEY (company_id) REFERENCES company (id),
  CONSTRAINT fk_design_request_creator FOREIGN KEY (created_by) REFERENCES user (id),
  CONSTRAINT fk_design_request_designer FOREIGN KEY (designer_id) REFERENCES user (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS design_request_item (
  id INT NOT NULL AUTO_INCREMENT,
  request_id INT NOT NULL,
  category ENUM('social_media','printing','video','mockup','identity','presentation','other') NOT NULL,
  title VARCHAR(255) NOT NULL,
  deadline DATE NULL,
  description TEXT NULL,
  size_h DECIMAL(12,2) NULL,
  size_w DECIMAL(12,2) NULL,
  size_l DECIMAL(12,2) NULL,
  quantity DECIMAL(12,2) NULL,
  unit VARCHAR(20) NULL,
  printing_type VARCHAR(30) NULL,
  duration VARCHAR(50) NULL,
  sort_order INT NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_design_request_item_request (request_id, sort_order),
  CONSTRAINT fk_design_request_item_request FOREIGN KEY (request_id) REFERENCES design_request (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- A brief file comes with the request (optionally on one item); a deliverable
-- is the designer's work, an uploaded file or a link.
CREATE TABLE IF NOT EXISTS design_request_file (
  id INT NOT NULL AUTO_INCREMENT,
  request_id INT NOT NULL,
  item_id INT NULL,
  kind ENUM('brief','deliverable') NOT NULL,
  file_url VARCHAR(500) NULL,
  link_url VARCHAR(1000) NULL,
  original_name VARCHAR(255) NULL,
  file_type VARCHAR(20) NULL,
  file_size INT NULL,
  uploaded_by INT NOT NULL,
  uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_design_request_file_request (request_id, kind),
  CONSTRAINT fk_design_request_file_request FOREIGN KEY (request_id) REFERENCES design_request (id) ON DELETE CASCADE,
  CONSTRAINT fk_design_request_file_item FOREIGN KEY (item_id) REFERENCES design_request_item (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS design_request_log (
  id INT NOT NULL AUTO_INCREMENT,
  request_id INT NOT NULL,
  actor_id INT NOT NULL,
  action VARCHAR(30) NOT NULL,
  note VARCHAR(1000) NULL,
  at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_design_request_log_request (request_id, id),
  CONSTRAINT fk_design_request_log_request FOREIGN KEY (request_id) REFERENCES design_request (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
