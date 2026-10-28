-- A discussion on a pending approval (Beshoy, 2026-10-28): the approver asks
-- the requester or their manager before deciding. A pending approval is not a
-- sales request yet, so the thread hangs off the approval; approving copies it
-- into the new request's comments.
CREATE TABLE IF NOT EXISTS approval_comment (
  id INT NOT NULL AUTO_INCREMENT,
  approval_id INT NOT NULL,
  user_id INT NOT NULL,
  body TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_approval_comment_approval (approval_id, id),
  CONSTRAINT fk_approval_comment_approval FOREIGN KEY (approval_id) REFERENCES sales_request_approvals (id) ON DELETE CASCADE,
  CONSTRAINT fk_approval_comment_user FOREIGN KEY (user_id) REFERENCES user (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Someone tagged with @ joins the discussion.
CREATE TABLE IF NOT EXISTS approval_comment_mention (
  comment_id INT NOT NULL,
  user_id INT NOT NULL,
  PRIMARY KEY (comment_id, user_id),
  CONSTRAINT fk_approval_mention_comment FOREIGN KEY (comment_id) REFERENCES approval_comment (id) ON DELETE CASCADE,
  CONSTRAINT fk_approval_mention_user FOREIGN KEY (user_id) REFERENCES user (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
