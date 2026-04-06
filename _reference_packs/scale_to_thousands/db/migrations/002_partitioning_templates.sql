-- Partitioning templates (optional but recommended at scale)
-- Use for high-volume tables: opportunities, send_events, auth_audit.
-- This is a template to convert existing tables with minimal downtime, typically during a maintenance window.

-- NOTE: Converting an existing large table to partitioned form requires:
-- 1) Create new partitioned table
-- 2) Create partitions (monthly)
-- 3) Copy data
-- 4) Swap tables (rename)
-- 5) Recreate indexes/constraints/triggers

-- Example partitioned send_events by month:

-- CREATE TABLE send_events_p (
--   LIKE send_events INCLUDING ALL
-- ) PARTITION BY RANGE (created_at);

-- CREATE TABLE send_events_2026_02 PARTITION OF send_events_p
--   FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

-- Repeat partitions monthly, and add an automation to create next month's partition.

-- When ready:
-- BEGIN;
-- ALTER TABLE send_events RENAME TO send_events_old;
-- ALTER TABLE send_events_p RENAME TO send_events;
-- COMMIT;
