# Prometheus and Grafana Setup

## Prometheus

- `/observability/prometheus` returns a scrape-safe text export.
- Prometheus is optional in deployment and not required for local development.

## Grafana

- `/observability/grafana` returns dashboard definitions.
- No external Grafana API is required for the current contract.

## Deployment

- Optional services are provided in `docker-compose.yml`.
- The stack remains safe to run without Prometheus or Grafana.
