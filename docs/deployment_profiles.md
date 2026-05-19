# Deployment Profiles

## local_dev

- Debug enabled
- Demo users enabled
- Auth optional in practice, but supported
- Telemetry fallback enabled
- Legacy routers disabled

## staging

- Debug disabled
- Demo users disabled by default
- Auth required
- Rate limiting enabled
- Telemetry fallback enabled
- Legacy routers disabled

## supervised_live

- Debug disabled
- Demo users disabled by default
- Auth required
- Rate limiting enabled
- Telemetry fallback enabled
- Legacy routers disabled

## production

- Debug disabled
- Demo users disabled by default
- Auth required
- Rate limiting enabled
- Telemetry fallback disabled unless explicitly configured
- Legacy routers disabled

## Safety defaults

- Manual-only submission
- Human-governed operator actions
- No autonomous workflow execution

