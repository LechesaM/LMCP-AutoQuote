-- Ranking fields for win-probability prioritization
BEGIN;

ALTER TABLE opportunities
  ADD COLUMN IF NOT EXISTS priority_score DOUBLE PRECISION DEFAULT 0,
  ADD COLUMN IF NOT EXISTS priority_band TEXT DEFAULT 'C',
  ADD COLUMN IF NOT EXISTS score_features JSONB;

CREATE INDEX IF NOT EXISTS opp_tenant_band_score_idx ON opportunities(tenant_id, priority_band, priority_score DESC);

COMMIT;
