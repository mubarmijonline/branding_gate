-- A quarter's target split across its three months (Gamal, 2026-11-02).
-- NULL means an even split; otherwise a JSON array of three amounts that
-- always adds up to `amount`. One-shot.
ALTER TABLE sales_target
    ADD COLUMN month_amounts JSON NULL COMMENT '[m1, m2, m3]; NULL = even split' AFTER amount;
