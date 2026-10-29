-- Design requests, round 2 (Gamal, 2026-10-30): work and approval per item,
-- the final file per item, and the job's sales request on the header.
-- Run once:  mysql branding_gate < design_request_items_flow_migration.sql

ALTER TABLE design_request
  ADD COLUMN sales_request_id INT NULL AFTER client_id,
  ADD INDEX idx_design_request_sr (sales_request_id);

ALTER TABLE design_request_item
  ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'open',
  ADD COLUMN submissions INT NOT NULL DEFAULT 0,
  ADD COLUMN submitted_at DATETIME NULL,
  ADD COLUMN decided_by INT NULL,
  ADD COLUMN decided_at DATETIME NULL,
  ADD COLUMN decision_note VARCHAR(1000) NULL,
  ADD COLUMN sent_by INT NULL,
  ADD COLUMN sent_at DATETIME NULL;

-- NULL while the designer is still working on it; the round it went out in after.
ALTER TABLE design_request_file
  ADD COLUMN submission INT NULL;

-- Requests made before: their items take the request's state, and work
-- already submitted counts as round 1.
UPDATE design_request_item i JOIN design_request r ON r.id = i.request_id
   SET i.status = CASE r.status
                    WHEN 'sent_to_operation' THEN 'sent'
                    WHEN 'approved' THEN 'approved'
                    WHEN 'in_review' THEN 'in_review'
                    WHEN 'changes' THEN 'changes'
                    ELSE 'open' END,
       i.submissions = IF(r.submitted_at IS NULL, 0, 1),
       i.submitted_at = r.submitted_at, i.decided_by = r.decided_by, i.decided_at = r.decided_at,
       i.decision_note = r.decision_note, i.sent_by = r.sent_by, i.sent_at = r.sent_at;

UPDATE design_request_file f JOIN design_request r ON r.id = f.request_id
   SET f.submission = 1
 WHERE f.kind = 'deliverable' AND r.submitted_at IS NOT NULL;
