# DB Migrations

Run these in order on your production database.

1) `001_add_tenant.sql` — Adds multi-tenant columns and a default tenant.
2) `002_partitioning_templates.sql` — Partition templates for high-volume tables (optional, recommended)
3) `003_indexes.sql` — Performance indexes for scale.
4) `004_ranking_columns.sql` — Adds ranking score/band/features for win-probability.

## How to apply
- Recommended: use a migration tool (Alembic/Flyway/Liquibase).
- MVP: apply manually in psql, with a backup snapshot first.
