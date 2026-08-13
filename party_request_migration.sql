-- Asking for a client or a supplier, rather than creating one.
--
-- Sales and Account Management meet clients; Operations and Purchasing meet
-- suppliers. Both now raise a request that their own department head passes and
-- an admin makes real, so nothing enters the books that two people have not
-- looked at.
--
-- One table for both, because the shape is identical -- somebody proposes a
-- record, two people sign, a row appears -- and one table means one queue, one
-- set of routes and one screen rather than two of everything. What differs is
-- the payload, which is the proposed record itself, kept as JSON so this table
-- never has to grow a column every time client or supplier does.
--
-- One-shot. Re-running fails on the existing table, which is safe. DDL commits
-- implicitly in MySQL, so this file is outside any transaction.

CREATE TABLE party_request (
    id                INT NOT NULL AUTO_INCREMENT,
    request_code      VARCHAR(20) NOT NULL,
    kind              ENUM('client', 'supplier') NOT NULL,
    -- The proposed record, exactly as it would be written. The approver sees
    -- all of it, not a name and a shrug.
    payload           JSON NOT NULL,
    status            ENUM('pending_head', 'pending_admin', 'approved',
                           'rejected', 'cancelled') NOT NULL DEFAULT 'pending_head',

    requested_by      INT NOT NULL,
    requested_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    note              VARCHAR(500) DEFAULT NULL COMMENT 'Why this one is worth adding',

    head_approved_by  INT DEFAULT NULL,
    head_approved_at  DATETIME DEFAULT NULL,
    head_notes        TEXT DEFAULT NULL,

    admin_approved_by INT DEFAULT NULL,
    admin_approved_at DATETIME DEFAULT NULL,
    admin_notes       TEXT DEFAULT NULL,

    rejected_by       INT DEFAULT NULL,
    rejected_at       DATETIME DEFAULT NULL,
    rejection_reason  TEXT DEFAULT NULL,

    -- The row this became, so the request and the record can be read together
    -- afterwards. Deliberately not a foreign key: deleting a client should not
    -- delete the history of it having been asked for.
    created_record_id INT DEFAULT NULL,

    PRIMARY KEY (id),
    UNIQUE KEY uq_party_request_code (request_code),
    KEY idx_party_request_status (status, kind),
    KEY idx_party_request_requester (requested_by),
    CONSTRAINT fk_party_request_requested_by FOREIGN KEY (requested_by) REFERENCES user (id),
    CONSTRAINT fk_party_request_head FOREIGN KEY (head_approved_by) REFERENCES user (id),
    CONSTRAINT fk_party_request_admin FOREIGN KEY (admin_approved_by) REFERENCES user (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
