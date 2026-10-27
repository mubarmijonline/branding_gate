-- Stickers: a company-wide pack anyone can add to, sent as a chat attachment.
ALTER TABLE chat_attachment MODIFY kind ENUM('image', 'voice', 'sticker') NOT NULL;

CREATE TABLE IF NOT EXISTS chat_sticker (
  id INT NOT NULL AUTO_INCREMENT,
  user_id INT NOT NULL COMMENT 'who added it',
  path VARCHAR(255) NOT NULL COMMENT 'under uploads/',
  mime VARCHAR(80) NOT NULL,
  bytes INT NOT NULL,
  width INT DEFAULT NULL,
  height INT DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_chat_sticker_live (is_deleted, id),
  CONSTRAINT fk_chat_sticker_user FOREIGN KEY (user_id) REFERENCES user (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
