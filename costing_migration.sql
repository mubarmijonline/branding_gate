-- Costing by assignment.
--
-- Cost stops being a field somebody types and becomes the outcome of a small
-- workflow: the Operations Head assigns an item to one or more team leaders,
-- each leader assigns it on to one or more of their own people, each of those
-- puts up one or more proposals with documents and images, and the leader who
-- asked accepts one. The accepted amount is written to
-- sales_request_items.cost_per_item, which is why nothing downstream -- pricing,
-- margins, the supplier report -- needs to know this workflow exists.
--
-- There is no "assigned to" column on the item: an item can be with several
-- people at once, which is a row per assignment, not a field.
--
-- One-shot. Re-running fails on the duplicate table, which is safe. DDL commits
-- implicitly in MySQL, so this file is deliberately outside any transaction.

CREATE TABLE costing_assignment (
    id            INT NOT NULL AUTO_INCREMENT,
    item_id       INT NOT NULL,
    request_id    INT NOT NULL,
    assignee_id   INT NOT NULL COMMENT 'Who has been asked to cost it',
    assigned_by   INT NOT NULL COMMENT 'Their manager, who decides their proposals',
    status        ENUM('open', 'withdrawn', 'closed') NOT NULL DEFAULT 'open',
    note          VARCHAR(500) DEFAULT NULL,
    added_date    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    -- The same person is asked once per item; asking again reopens that row
    -- rather than leaving two live assignments to reconcile.
    UNIQUE KEY uq_costing_assignment (item_id, assignee_id),
    KEY idx_costing_assignment_assignee (assignee_id, status),
    KEY idx_costing_assignment_request (request_id),
    CONSTRAINT fk_costing_assignment_item FOREIGN KEY (item_id)
        REFERENCES sales_request_items (id) ON DELETE CASCADE,
    CONSTRAINT fk_costing_assignment_request FOREIGN KEY (request_id)
        REFERENCES sales_request (id) ON DELETE CASCADE,
    CONSTRAINT fk_costing_assignment_assignee FOREIGN KEY (assignee_id)
        REFERENCES user (id),
    CONSTRAINT fk_costing_assignment_by FOREIGN KEY (assigned_by)
        REFERENCES user (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE costing_proposal (
    id            INT NOT NULL AUTO_INCREMENT,
    item_id       INT NOT NULL,
    request_id    INT NOT NULL,
    assignment_id INT NOT NULL,
    author_id     INT NOT NULL,
    amount        DECIMAL(15, 2) NOT NULL COMMENT 'Proposed cost per item',
    notes         TEXT,
    status        ENUM('submitted', 'accepted', 'rejected', 'withdrawn')
                  NOT NULL DEFAULT 'submitted',
    decided_by    INT DEFAULT NULL,
    decided_at    DATETIME DEFAULT NULL,
    decision_note VARCHAR(500) DEFAULT NULL,
    added_date    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_costing_proposal_item (item_id, status),
    KEY idx_costing_proposal_author (author_id),
    KEY idx_costing_proposal_assignment (assignment_id),
    CONSTRAINT fk_costing_proposal_item FOREIGN KEY (item_id)
        REFERENCES sales_request_items (id) ON DELETE CASCADE,
    CONSTRAINT fk_costing_proposal_request FOREIGN KEY (request_id)
        REFERENCES sales_request (id) ON DELETE CASCADE,
    CONSTRAINT fk_costing_proposal_assignment FOREIGN KEY (assignment_id)
        REFERENCES costing_assignment (id) ON DELETE CASCADE,
    CONSTRAINT fk_costing_proposal_author FOREIGN KEY (author_id)
        REFERENCES user (id),
    CONSTRAINT fk_costing_proposal_decider FOREIGN KEY (decided_by)
        REFERENCES user (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

-- Files hang off the proposal, not the item: a quotation belongs to the offer
-- it justifies, and deleting a proposal should take its evidence with it.
CREATE TABLE costing_proposal_file (
    id            INT NOT NULL AUTO_INCREMENT,
    proposal_id   INT NOT NULL,
    file_url      VARCHAR(500) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    file_type     VARCHAR(100) DEFAULT NULL,
    file_size     INT DEFAULT NULL,
    uploaded_by   INT DEFAULT NULL,
    uploaded_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_costing_file_proposal (proposal_id),
    CONSTRAINT fk_costing_file_proposal FOREIGN KEY (proposal_id)
        REFERENCES costing_proposal (id) ON DELETE CASCADE,
    CONSTRAINT fk_costing_file_uploader FOREIGN KEY (uploaded_by)
        REFERENCES user (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

-- Every step, kept even when the assignment or proposal it refers to is gone,
-- which is why nothing here cascades.
CREATE TABLE costing_log (
    id          INT NOT NULL AUTO_INCREMENT,
    item_id     INT NOT NULL,
    request_id  INT NOT NULL,
    proposal_id INT DEFAULT NULL,
    actor_id    INT NOT NULL,
    action      VARCHAR(40) NOT NULL,
    detail      VARCHAR(1000) DEFAULT NULL,
    amount      DECIMAL(15, 2) DEFAULT NULL,
    added_date  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_costing_log_item (item_id, added_date),
    KEY idx_costing_log_request (request_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
