-- Client invoices: the item list, the invoice and its lines.
--
-- An account manager drafts an invoice from a Sales Request and sends it to
-- Finance; Finance posts it, which gives it its number and puts it on the
-- client's account. Arithmetic lives in invoicing.py.
--
-- One-shot. Re-running fails on the existing tables, which is safe.

CREATE TABLE invoice_catalog (
    id INT NOT NULL AUTO_INCREMENT,
    code INT NOT NULL,
    name_ar VARCHAR(200) NOT NULL,
    name_en VARCHAR(200) NOT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_by INT DEFAULT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_invoice_catalog_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE client_invoice (
    id INT NOT NULL AUTO_INCREMENT,
    invoice_number INT DEFAULT NULL,
    status ENUM('draft', 'submitted', 'posted', 'returned', 'cancelled') NOT NULL DEFAULT 'draft',
    sales_request_id INT DEFAULT NULL,
    company_id INT DEFAULT NULL,
    client_id INT DEFAULT NULL,
    invoice_date DATE NOT NULL,
    billing_month CHAR(7) NOT NULL,
    vat_rate DECIMAL(5,2) NOT NULL DEFAULT 14.00,
    profit_tax_rate DECIMAL(5,2) NOT NULL DEFAULT 1.00,
    apply_profit_tax TINYINT(1) NOT NULL DEFAULT 1,
    subtotal DECIMAL(15,2) NOT NULL DEFAULT 0,
    cash_discount_total DECIMAL(15,2) NOT NULL DEFAULT 0,
    vat_total DECIMAL(15,2) NOT NULL DEFAULT 0,
    profit_tax_total DECIMAL(15,2) NOT NULL DEFAULT 0,
    total DECIMAL(15,2) NOT NULL DEFAULT 0,
    notes TEXT,
    created_by INT DEFAULT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    submitted_at DATETIME DEFAULT NULL,
    posted_by INT DEFAULT NULL,
    posted_at DATETIME DEFAULT NULL,
    returned_by INT DEFAULT NULL,
    returned_at DATETIME DEFAULT NULL,
    return_reason VARCHAR(500) DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_client_invoice_number (invoice_number),
    KEY idx_client_invoice_company (company_id, status),
    KEY idx_client_invoice_client (client_id, status),
    KEY idx_client_invoice_sr (sales_request_id),
    CONSTRAINT fk_client_invoice_sr FOREIGN KEY (sales_request_id) REFERENCES sales_request (id) ON DELETE SET NULL,
    CONSTRAINT fk_client_invoice_company FOREIGN KEY (company_id) REFERENCES company (id) ON DELETE SET NULL,
    CONSTRAINT fk_client_invoice_client FOREIGN KEY (client_id) REFERENCES client (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE client_invoice_line (
    id INT NOT NULL AUTO_INCREMENT,
    invoice_id INT NOT NULL,
    line_no INT NOT NULL,
    catalog_id INT DEFAULT NULL,
    item_code INT DEFAULT NULL,
    name_ar VARCHAR(200) DEFAULT NULL,
    name_en VARCHAR(200) DEFAULT NULL,
    description VARCHAR(500) DEFAULT NULL,
    qty DECIMAL(12,2) NOT NULL DEFAULT 1,
    unit_price DECIMAL(15,2) NOT NULL DEFAULT 0,
    cash_discount DECIMAL(15,2) NOT NULL DEFAULT 0,
    sales_value DECIMAL(15,2) NOT NULL DEFAULT 0,
    vat DECIMAL(15,2) NOT NULL DEFAULT 0,
    line_total DECIMAL(15,2) NOT NULL DEFAULT 0,
    sales_request_item_id INT DEFAULT NULL,
    PRIMARY KEY (id),
    KEY idx_client_invoice_line_invoice (invoice_id, line_no),
    CONSTRAINT fk_client_invoice_line_invoice FOREIGN KEY (invoice_id) REFERENCES client_invoice (id) ON DELETE CASCADE,
    CONSTRAINT fk_client_invoice_line_catalog FOREIGN KEY (catalog_id) REFERENCES invoice_catalog (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
