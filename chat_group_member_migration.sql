-- People added to a chat group by hand, on top of the ones the group's rule
-- brings in (role level, department). Removing a row takes out only what was
-- added; the rule's members cannot be removed.
CREATE TABLE IF NOT EXISTS chat_group_member (
  room VARCHAR(40) NOT NULL,
  user_id INT NOT NULL,
  added_by INT NOT NULL,
  added_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (room, user_id),
  CONSTRAINT fk_chat_group_member_user FOREIGN KEY (user_id) REFERENCES user (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
