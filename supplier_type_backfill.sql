-- The supplier type that was stored as the word "Other".
--
-- Choosing "Other" and typing a real type stored **Other** as the type, with
-- the typed word parked in other_supplier_type, which no list, filter or
-- report reads. So those suppliers all showed as "Other" and the answer the
-- user actually gave was invisible.
--
-- The typed word is the type. other_supplier_type keeps it as a note of how
-- it arrived, which is also what makes it show up in the dropdown from now on.

UPDATE supplier
   SET supplier_type = TRIM(other_supplier_type)
 WHERE LOWER(TRIM(supplier_type)) = 'other'
   AND other_supplier_type IS NOT NULL
   AND TRIM(other_supplier_type) <> '';
