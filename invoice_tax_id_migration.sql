-- The Tax ID of a client invoice (Ahmed, 2026-11-11): the number the tax
-- authority gives the e-invoice. Finance enters it when posting; it shows in
-- the journal, the client's statement and the printed invoice.
ALTER TABLE client_invoice ADD COLUMN tax_id VARCHAR(100) NULL AFTER invoice_number,
    ADD UNIQUE KEY uq_client_invoice_tax_id (tax_id);
