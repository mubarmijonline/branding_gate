-- Chat: photos and voice notes on a message, and who has seen what.
-- A thread is 'sr:<request id>' or 'g:<room>'. The message id is the row id in
-- sales_request_comments or group_chat_message.
CREATE TABLE IF NOT EXISTS chat_attachment (
  id INT NOT NULL AUTO_INCREMENT,
  thread VARCHAR(40) NOT NULL,
  message_id INT NOT NULL,
  user_id INT NOT NULL,
  kind ENUM('image', 'voice') NOT NULL,
  path VARCHAR(255) NOT NULL COMMENT 'under uploads/',
  mime VARCHAR(80) NOT NULL,
  bytes INT NOT NULL,
  duration_ms INT DEFAULT NULL,
  width INT DEFAULT NULL,
  height INT DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_chat_attachment_message (thread, message_id),
  CONSTRAINT fk_chat_attachment_user FOREIGN KEY (user_id) REFERENCES user (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- One row each time a person's "seen up to" moves forward in a thread, so the
-- time each message was first seen is the first row that reaches it.
CREATE TABLE IF NOT EXISTS chat_seen (
  thread VARCHAR(40) NOT NULL,
  user_id INT NOT NULL,
  upto_id INT NOT NULL,
  seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (thread, user_id, upto_id),
  KEY idx_chat_seen_user (user_id, thread)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- What the group rooms already knew about reading.
INSERT IGNORE INTO chat_seen (thread, user_id, upto_id, seen_at)
SELECT CONCAT('g:', room), user_id, last_read_id, NOW() FROM group_chat_read WHERE last_read_id > 0;

-- An author has seen their own messages.
INSERT IGNORE INTO chat_seen (thread, user_id, upto_id, seen_at)
SELECT CONCAT('g:', room), user_id, MAX(id), MAX(created_at) FROM group_chat_message GROUP BY room, user_id;
INSERT IGNORE INTO chat_seen (thread, user_id, upto_id, seen_at)
SELECT CONCAT('sr:', request_id), user_id, MAX(id), MAX(created_at) FROM sales_request_comments
WHERE is_deleted = 0 GROUP BY request_id, user_id;
