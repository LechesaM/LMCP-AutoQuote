# Sentry Runtime Monitoring

Sentry support is optional and disabled unless explicitly configured.

## Environment

- `LMCP_SENTRY_DSN`
- `LMCP_ENABLE_SENTRY`

## Behaviour

- If the DSN is missing, Sentry remains disabled.
- Runtime exception capture includes request IDs and correlation IDs.
- No secrets or tokens are written into observability payloads.
