-- An item's identity belongs to its entity.
--
-- idx_unique_item spanned (item_name, unit_of_measure, width, height, depth,
-- is_credit_item) across the whole table, so two entities could not both hold
-- a "Mug Sublimation White" -- even though every list, every filter and every
-- statistic on the inventory page is scoped to one entity. One entity adding
-- an item silently took that name away from all the others.
--
-- The entity joins the key. A retired row still holds its slot, which is
-- deliberate: adding the same item again brings that row back with its
-- transaction history rather than starting a second one beside it.
--
-- One-shot. DDL commits implicitly in MySQL, so this file is deliberately
-- outside any transaction.

ALTER TABLE inventory_items
    DROP INDEX idx_unique_item,
    ADD UNIQUE KEY idx_unique_item
        (entity_id, item_name, unit_of_measure, width, height, depth, is_credit_item);
