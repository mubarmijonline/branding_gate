-- A sales request saved as a draft (Gamal, 2026-10-28): the form as it
-- stood, kept on the server for its author. Its own table, so nothing that
-- reads sales_request (Operation, Pricing, approvals, counts) can see it.
-- Launching it submits the form normally and deletes the draft.
CREATE TABLE IF NOT EXISTS sales_request_draft (
  id INT NOT NULL AUTO_INCREMENT,
  user_id INT NOT NULL,
  title VARCHAR(255) NULL,
  snapshot JSON NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_sales_request_draft_user (user_id, updated_at),
  CONSTRAINT fk_sales_request_draft_user FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
