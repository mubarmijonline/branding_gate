-- A supplier's balance brought forward (رصيد أول المدة) from before the system.
--
-- A positive amount is what we owe the supplier, a negative one is what they
-- owe us (an advance we paid). It opens their statement. Set by Finance.
--
-- One-shot. Re-running fails on the existing table, which is safe.

CREATE TABLE supplier_opening_balance (
    id INT NOT NULL AUTO_INCREMENT,
    supplier_id INT NOT NULL,
    as_of DATE NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    note VARCHAR(300) DEFAULT NULL,
    created_by INT DEFAULT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_supplier_opening_supplier (supplier_id),
    CONSTRAINT fk_supplier_opening_supplier FOREIGN KEY (supplier_id) REFERENCES supplier (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
