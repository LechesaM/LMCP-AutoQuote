-- Multi-tenant support (safe defaults)
-- Creates a tenants table and adds tenant_id to key tables.
-- If you are single-tenant only, you can still keep tenant_id fixed = 1.

BEGIN;

CREATE TABLE IF NOT EXISTS tenants (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ DEFAULT now()
);

INSERT INTO tenants (name) VALUES ('default') ON CONFLICT (name) DO NOTHING;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS tenant_id BIGINT;

UPDATE users SET tenant_id = (SELECT id FROM tenants WHERE name='default') WHERE tenant_id IS NULL;

ALTER TABLE users
  ALTER COLUMN tenant_id SET NOT NULL;

ALTER TABLE opportunities
  ADD COLUMN IF NOT EXISTS tenant_id BIGINT;

UPDATE opportunities SET tenant_id = (SELECT id FROM tenants WHERE name='default') WHERE tenant_id IS NULL;

ALTER TABLE opportunities
  ALTER COLUMN tenant_id SET NOT NULL;

ALTER TABLE send_events
  ADD COLUMN IF NOT EXISTS tenant_id BIGINT;

UPDATE send_events SET tenant_id = (SELECT id FROM tenants WHERE name='default') WHERE tenant_id IS NULL;

ALTER TABLE send_events
  ALTER COLUMN tenant_id SET NOT NULL;

ALTER TABLE soe_entities
  ADD COLUMN IF NOT EXISTS tenant_id BIGINT;

UPDATE soe_entities SET tenant_id = (SELECT id FROM tenants WHERE name='default') WHERE tenant_id IS NULL;

ALTER TABLE soe_entities
  ALTER COLUMN tenant_id SET NOT NULL;

ALTER TABLE soe_aliases
  ADD COLUMN IF NOT EXISTS tenant_id BIGINT;

UPDATE soe_aliases SET tenant_id = (SELECT id FROM tenants WHERE name='default') WHERE tenant_id IS NULL;

ALTER TABLE soe_aliases
  ALTER COLUMN tenant_id SET NOT NULL;

ALTER TABLE soe_allowlist_recipients
  ADD COLUMN IF NOT EXISTS tenant_id BIGINT;

UPDATE soe_allowlist_recipients SET tenant_id = (SELECT id FROM tenants WHERE name='default') WHERE tenant_id IS NULL;

ALTER TABLE soe_allowlist_recipients
  ALTER COLUMN tenant_id SET NOT NULL;

ALTER TABLE soe_policy_overrides
  ADD COLUMN IF NOT EXISTS tenant_id BIGINT;

UPDATE soe_policy_overrides SET tenant_id = (SELECT id FROM tenants WHERE name='default') WHERE tenant_id IS NULL;

ALTER TABLE soe_policy_overrides
  ALTER COLUMN tenant_id SET NOT NULL;

COMMIT;
