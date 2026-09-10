-- Who last touched an item, and what they did to it.
--
-- `created_by` was the only trace an inventory item carried, and it held a
-- bare username: no mobile, no user id, and nothing at all about the edits
-- after the first save. The page could say who made the row and never who
-- changed its minimum yesterday.
--
-- Two additions. `updated_by` on the item, alongside the `updated_at` that was
-- already there, and one table for the timeline -- created, edited, retired,
-- restored -- recorded field by field so the item can show what changed, from
-- what, to what, and by whom.

ALTER TABLE inventory_items
    ADD COLUMN updated_by VARCHAR(100) NULL AFTER created_by;

UPDATE inventory_items SET updated_by = created_by WHERE updated_by IS NULL;

CREATE TABLE IF NOT EXISTS inventory_item_events (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    item_id         INT NOT NULL,
    event_type      ENUM('created','edited','retired','restored','deleted') NOT NULL,
    field_name      VARCHAR(64) NULL,
    old_value       VARCHAR(255) NULL,
    new_value       VARCHAR(255) NULL,
    note            VARCHAR(255) NULL,
    performed_by    VARCHAR(100) NULL,
    performed_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_item_events_item (item_id, performed_at),
    CONSTRAINT fk_item_events_item FOREIGN KEY (item_id)
        REFERENCES inventory_items (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Every item that already exists was created by somebody, at a time the row
-- still remembers, so the timeline does not start empty.
INSERT INTO inventory_item_events (item_id, event_type, note, performed_by, performed_at)
SELECT id, 'created', CONCAT('Item ', item_code, ' added'), created_by, created_at
FROM inventory_items
WHERE NOT EXISTS (
    SELECT 1 FROM inventory_item_events e
    WHERE e.item_id = inventory_items.id AND e.event_type = 'created'
);
