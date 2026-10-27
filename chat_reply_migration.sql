-- Reply to a message in a group room (request chats already have
-- sales_request_comments.parent_comment_id).
ALTER TABLE group_chat_message ADD COLUMN reply_to_id INT NULL AFTER body;
