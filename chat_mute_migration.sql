-- A person's muted chats: no sound, no pop-up, and a muted group's unread
-- count stays out of the chat badge. NULL muted_until = muted until unmuted.
CREATE TABLE IF NOT EXISTS chat_mute (
  user_id INT NOT NULL,
  thread VARCHAR(40) NOT NULL,
  muted_until DATETIME DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, thread),
  CONSTRAINT fk_chat_mute_user FOREIGN KEY (user_id) REFERENCES user (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
