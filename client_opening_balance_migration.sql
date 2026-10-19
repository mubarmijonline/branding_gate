-- A client's balance brought forward (رصيد أول المدة) from before the system.
--
-- One row per client (or per company, when client_id is NULL) and date. A
-- positive amount is owed by the client (debit), a negative one is owed to
-- them. It opens their statement of account. Set by Finance.
--
-- One-shot. Re-running fails on the existing table, which is safe.

CREATE TABLE client_opening_balance (
    id INT NOT NULL AUTO_INCREMENT,
    company_id INT DEFAULT NULL,
    client_id INT DEFAULT NULL,
    as_of DATE NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    note VARCHAR(300) DEFAULT NULL,
    created_by INT DEFAULT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_client_opening_company (company_id),
    KEY idx_client_opening_client (client_id),
    CONSTRAINT fk_client_opening_company FOREIGN KEY (company_id) REFERENCES company (id) ON DELETE CASCADE,
    CONSTRAINT fk_client_opening_client FOREIGN KEY (client_id) REFERENCES client (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
