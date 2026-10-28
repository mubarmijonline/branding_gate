-- Design requests (WhatsApp request #1, Gamal Gaber, 28 Oct 2026).
--
-- An Account Manager, Sales person or Marketing person asks the design team
-- for work: one shared header (company, client, event date, deadline) and one
-- or more items, each in a category with that category's fields. The design
-- head assigns a designer, the designer delivers a file or a link, the head
-- approves or sends it back, and the requester takes an approved design on to
-- Operations. `designer_kind` says which team (2D now, 3D next) so the 3D flow
-- is the same tables with another value, not a second copy.
--
-- One-shot. Re-running fails on the duplicate table, which is safe. DDL commits
-- implicitly in MySQL, so this file is deliberately outside any transaction.
--
-- PENDING: not applied to the live database yet (see CLAUDE.md).

CREATE TABLE design_request (
    id              INT NOT NULL AUTO_INCREMENT,
    designer_kind   ENUM('2d', '3d') NOT NULL DEFAULT '2d',
    company_id      INT DEFAULT NULL,
    client_id       INT DEFAULT NULL,
    event_date      DATE DEFAULT NULL,
    deadline        DATE DEFAULT NULL,
    notes           TEXT,
    status          ENUM('submitted', 'assigned', 'delivered', 'approved',
                         'rejected', 'sent_to_operation')
                    NOT NULL DEFAULT 'submitted',
    -- The requester. Every list is scoped on this column, the same way
    -- sales_request.owner_user_id scopes the sales pages.
    owner_user_id   INT NOT NULL,
    assignee_id     INT DEFAULT NULL COMMENT 'The designer it is with',
    assigned_by     INT DEFAULT NULL,
    assigned_at     DATETIME DEFAULT NULL,
    delivered_at    DATETIME DEFAULT NULL,
    delivery_note   VARCHAR(1000) DEFAULT NULL,
    decided_by      INT DEFAULT NULL,
    decided_at      DATETIME DEFAULT NULL,
    decision_note   VARCHAR(1000) DEFAULT NULL COMMENT 'The reason, when sent back',
    sent_to_operation_by INT DEFAULT NULL,
    sent_to_operation_at DATETIME DEFAULT NULL,
    added_date      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_design_request_owner (owner_user_id, status),
    KEY idx_design_request_assignee (assignee_id, status),
    KEY idx_design_request_kind (designer_kind, status),
    CONSTRAINT fk_design_request_company FOREIGN KEY (company_id)
        REFERENCES company (id) ON DELETE SET NULL,
    CONSTRAINT fk_design_request_client FOREIGN KEY (client_id)
        REFERENCES client (id) ON DELETE SET NULL,
    CONSTRAINT fk_design_request_owner FOREIGN KEY (owner_user_id)
        REFERENCES user (id),
    CONSTRAINT fk_design_request_assignee FOREIGN KEY (assignee_id)
        REFERENCES user (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE design_request_item (
    id              INT NOT NULL AUTO_INCREMENT,
    request_id      INT NOT NULL,
    category        ENUM('social_media', 'printing_production', 'video',
                         'mockup_reference', 'identity', 'presentation', 'other')
                    NOT NULL,
    title           VARCHAR(200) NOT NULL,
    deadline        DATE DEFAULT NULL,
    description     TEXT,
    -- Printing & Production (and Other): centimetres and units.
    size_h          DECIMAL(10, 2) DEFAULT NULL,
    size_w          DECIMAL(10, 2) DEFAULT NULL,
    size_l          DECIMAL(10, 2) DEFAULT NULL,
    quantity        INT DEFAULT NULL,
    -- The word, not a code: Vinyl / Banner / Laser / Digital / Silkscreen / UV
    -- are offered, and anything typed under "other" is stored as typed.
    printing_type   VARCHAR(60) DEFAULT NULL,
    -- Video (and Other).
    duration        VARCHAR(60) DEFAULT NULL,
    sort_order      INT NOT NULL DEFAULT 0,
    added_date      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_design_request_item_request (request_id),
    CONSTRAINT fk_design_request_item_request FOREIGN KEY (request_id)
        REFERENCES design_request (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE design_request_file (
    id              INT NOT NULL AUTO_INCREMENT,
    request_id      INT NOT NULL,
    item_id         INT DEFAULT NULL COMMENT 'NULL for a deliverable on the whole request',
    kind            ENUM('brief', 'deliverable') NOT NULL DEFAULT 'brief',
    file_url        VARCHAR(500) DEFAULT NULL COMMENT '/uploads/design/<request>/<file>',
    link_url        VARCHAR(1000) DEFAULT NULL COMMENT 'A deliverable given as a link',
    original_name   VARCHAR(255) DEFAULT NULL,
    file_type       VARCHAR(20) DEFAULT NULL,
    file_size       INT DEFAULT NULL,
    uploaded_by     INT NOT NULL,
    uploaded_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_design_request_file_request (request_id, kind),
    KEY idx_design_request_file_item (item_id),
    CONSTRAINT fk_design_request_file_request FOREIGN KEY (request_id)
        REFERENCES design_request (id) ON DELETE CASCADE,
    CONSTRAINT fk_design_request_file_item FOREIGN KEY (item_id)
        REFERENCES design_request_item (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE design_request_log (
    id              INT NOT NULL AUTO_INCREMENT,
    request_id      INT NOT NULL,
    actor_id        INT NOT NULL,
    action          ENUM('submitted', 'assigned', 'reassigned', 'delivered',
                         'approved', 'rejected', 'sent_to_operation',
                         'file_attached') NOT NULL,
    detail          VARCHAR(1000) DEFAULT NULL,
    added_date      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_design_request_log_request (request_id, added_date),
    CONSTRAINT fk_design_request_log_request FOREIGN KEY (request_id)
        REFERENCES design_request (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

-- Then: branding_gate_VENV/bin/python seed_rbac.py   (the six design_request.* grants)
