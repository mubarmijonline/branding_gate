-- Alternative options on an item.
--
-- Sales describe what the client asked for. Costing frequently knows a second
-- way to do it -- a different supplier, a different material, a cheaper build
-- -- and until now the only place to say so was a sentence in a proposal note,
-- with the photograph attached to that proposal where nobody downstream looked.
--
-- An alternative is therefore a picture of the item with a comment, hanging off
-- the item itself, marked as an alternative so it can never be mistaken for
-- what sales specified. Pricing and the client then see "this, or this".
--
-- It goes on item_images because that is the table both the operations cost
-- modal and the sales request detail already read, so an alternative reaches
-- every page that shows the item without a second query being added anywhere.
--
-- One-shot. DDL commits implicitly in MySQL, so this file is deliberately
-- outside any transaction.

ALTER TABLE item_images
    ADD COLUMN is_alternative TINYINT(1) NOT NULL DEFAULT 0
        COMMENT 'Costing''s alternative option, not what sales specified',
    ADD COLUMN alt_comment VARCHAR(1000) DEFAULT NULL
        COMMENT 'Why this alternative, in the words of whoever proposed it',
    ADD COLUMN alt_label VARCHAR(120) DEFAULT NULL
        COMMENT 'Short name for the option, e.g. "Aluminium frame"',
    ADD KEY idx_item_images_alternative (item_id, is_alternative);
