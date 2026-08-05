-- Quarterly sales targets, and named teams for the branches they follow.
--
-- A target is one amount for one person for one quarter, set by that person's
-- manager. The tree is the reporting line already in `user.manager_id`, so
-- there is no parent column here: a target's parent is the target of
-- `user.manager_id` for the same period. Nothing to keep in sync when someone
-- changes manager.
--
-- A team is a named branch: the leader plus whoever reports to them. `team`
-- already existed and was read by nothing (CLAUDE.md: retired with the legacy
-- role system), so it is reused rather than replaced -- one leader per row,
-- membership derived, never stored.
--
-- One-shot. Re-running fails on the duplicate column/table, which is safe.
-- DDL commits implicitly in MySQL, so this file is deliberately outside any
-- transaction.

ALTER TABLE team
    ADD COLUMN leader_id INT NULL AFTER department_id,
    ADD UNIQUE KEY uq_team_leader (leader_id),
    ADD CONSTRAINT fk_team_leader FOREIGN KEY (leader_id) REFERENCES user (id);

-- The four surviving rows name teams that no longer exist and hold a leader of
-- NULL, which the unique key permits any number of. They are ignored by every
-- query here (all of which join on leader_id) and are left in place rather
-- than deleted, matching how `role_legacy` was retired.

CREATE TABLE sales_target (
    id            INT NOT NULL AUTO_INCREMENT,
    user_id       INT NOT NULL,
    period        CHAR(7) NOT NULL COMMENT 'Quarter, as 2026-Q3',
    amount        DECIMAL(15, 2) NOT NULL,
    assigned_by   INT NOT NULL COMMENT 'The manager who set it',
    note          VARCHAR(255) DEFAULT NULL,
    added_date    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_target_user_period (user_id, period),
    KEY idx_target_period (period),
    CONSTRAINT fk_target_user FOREIGN KEY (user_id) REFERENCES user (id),
    CONSTRAINT fk_target_assigner FOREIGN KEY (assigned_by) REFERENCES user (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
