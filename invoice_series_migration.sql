-- Where the invoice series continues from. Finance's paper invoices already
-- run past 2452, so the system's first invoice must not be 1. The next number
-- is the larger of this and the highest number used + 1.
--
-- One-shot. Re-running fails on the existing table, which is safe.

CREATE TABLE invoice_series (
    id TINYINT NOT NULL,
    next_number INT NOT NULL DEFAULT 1,
    updated_by INT DEFAULT NULL,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO invoice_series (id, next_number) VALUES (1, 1);
