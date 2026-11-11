-- A supplier assignment waits for Finance (Ahmed, 2026-11-11): the item's
-- cost becomes owed to the supplier (5101 / 2101) only once Finance approves.
-- Operations asks with the supplier, the due date, a note and documents.
CREATE TABLE IF NOT EXISTS supplier_assignment_request (
    id INT NOT NULL AUTO_INCREMENT,
    item_id INT NOT NULL,
    request_id INT NOT NULL,
    supplier_id INT NULL,
    previous_supplier_id INT NULL,
    due_date DATE NULL,
    item_cost DECIMAL(14,2) NULL,
    note VARCHAR(1000) NULL,
    status ENUM('pending','approved','rejected','cancelled') NOT NULL DEFAULT 'pending',
    requested_by INT NOT NULL,
    requested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by INT NULL,
    decided_at DATETIME NULL,
    decision_note VARCHAR(1000) NULL,
    PRIMARY KEY (id),
    KEY idx_sar_item (item_id, status),
    KEY idx_sar_status (status),
    CONSTRAINT fk_sar_item FOREIGN KEY (item_id) REFERENCES sales_request_items (id) ON DELETE CASCADE,
    CONSTRAINT fk_sar_supplier FOREIGN KEY (supplier_id) REFERENCES supplier (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS supplier_assignment_file (
    id INT NOT NULL AUTO_INCREMENT,
    assignment_id INT NOT NULL,
    stored_path VARCHAR(500) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(100) NULL,
    file_size INT NULL,
    uploaded_by INT NULL,
    uploaded_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_saf_assignment (assignment_id),
    CONSTRAINT fk_saf_assignment FOREIGN KEY (assignment_id) REFERENCES supplier_assignment_request (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Agreed vs actual cost (Ahmed, 2026-11-11): the item's costing is the agreed
-- number; Operations can put a different actual cost with the supplier. Above
-- agreed, the Operations head approves first (pending_head); Finance books the
-- actual cost, kept on the item as supplier_cost.
ALTER TABLE supplier_assignment_request
    MODIFY status ENUM('pending_head','pending','approved','rejected','cancelled') NOT NULL DEFAULT 'pending',
    ADD COLUMN actual_cost DECIMAL(14,2) NULL AFTER item_cost,
    ADD COLUMN head_by INT NULL AFTER decision_note,
    ADD COLUMN head_at DATETIME NULL AFTER head_by,
    ADD COLUMN head_note VARCHAR(1000) NULL AFTER head_at;
ALTER TABLE sales_request_items ADD COLUMN supplier_cost DECIMAL(14,2) NULL AFTER total_cost;
