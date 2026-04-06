-- Performance indexes for scale
BEGIN;

-- Opportunities
CREATE INDEX IF NOT EXISTS opp_tenant_status_dt_idx ON opportunities(tenant_id, status, closing_dt);
CREATE INDEX IF NOT EXISTS opp_tenant_soe_idx ON opportunities(tenant_id, soe_id);
CREATE INDEX IF NOT EXISTS opp_tenant_created_idx ON opportunities(tenant_id, created_at);

-- Send events
CREATE INDEX IF NOT EXISTS send_tenant_status_idx ON send_events(tenant_id, status);
CREATE INDEX IF NOT EXISTS send_tenant_created_idx ON send_events(tenant_id, created_at);

-- SOE matching
CREATE INDEX IF NOT EXISTS soe_entity_tenant_idx ON soe_entities(tenant_id);
CREATE INDEX IF NOT EXISTS soe_alias_norm_idx ON soe_aliases(tenant_id, normalized_alias);

COMMIT;
