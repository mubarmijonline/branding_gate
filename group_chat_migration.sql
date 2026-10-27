-- Group chats (Managers, Operations, Sales) beside the per-request chats.
-- Who belongs to a room is decided in code from role level and department.
CREATE TABLE IF NOT EXISTS group_chat_message (
  id INT NOT NULL AUTO_INCREMENT,
  room VARCHAR(20) NOT NULL,
  user_id INT NOT NULL,
  body TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_group_chat_room (room, id),
  CONSTRAINT fk_group_chat_user FOREIGN KEY (user_id) REFERENCES user (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS group_chat_read (
  room VARCHAR(20) NOT NULL,
  user_id INT NOT NULL,
  last_read_id INT NOT NULL DEFAULT 0,
  PRIMARY KEY (room, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
