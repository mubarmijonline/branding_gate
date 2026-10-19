-- Refund invoices (credit notes), and the money that moves when Finance posts.
--
-- A refund is a client_invoice of kind 'refund' raised against a posted
-- invoice, for some of its lines and quantities; it has its own number series
-- and is a credit on the client's statement. Posting either kind records the
-- money received (invoice) or paid back (refund) in a payment method, so it
-- reaches the payment method balances and Finance's reports.
--
-- One-shot. Re-running fails on the duplicate columns, which is safe.

ALTER TABLE client_invoice
    ADD COLUMN kind ENUM('invoice', 'refund') NOT NULL DEFAULT 'invoice' AFTER id,
    ADD COLUMN refund_of INT DEFAULT NULL AFTER kind,
    ADD COLUMN payment_transaction_id INT DEFAULT NULL,
    DROP INDEX uq_client_invoice_number,
    ADD UNIQUE KEY uq_client_invoice_kind_number (kind, invoice_number),
    ADD KEY idx_client_invoice_refund_of (refund_of),
    ADD CONSTRAINT fk_client_invoice_refund_of FOREIGN KEY (refund_of) REFERENCES client_invoice (id);

ALTER TABLE client_invoice_line
    ADD COLUMN refund_of_line INT DEFAULT NULL,
    ADD KEY idx_client_invoice_line_refund_of (refund_of_line);

-- The refund series, beside the invoice series (id 1).
INSERT INTO invoice_series (id, next_number) VALUES (2, 1);

-- Where money paid back to a client is booked.
INSERT INTO finance_categories (category_name, category_code, category_type, description, is_system, is_active, display_order)
VALUES ('Client Refunds | مرتجعات العملاء', 'CLIENT_REFUNDS', 'expense', 'Money paid back to a client against a refund invoice', 1, 1, 18);
