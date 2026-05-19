# Production Deployment And Auth

LMCP AutoQuote is deployed as a governed, human-controlled procurement operations platform.

## Deployment overview

- Backend: FastAPI application with read-only telemetry and governed operator actions.
- Frontend: Command Centre Vite build served as a static bundle.
- Authentication: JWT-backed sessions with RBAC enforced in the backend.
- Operator actions: explicit, audited, and reviewable only.

## Authentication overview

- Login endpoint: `POST /auth/login`
- Session endpoint: `GET /auth/me`
- Permission endpoint: `GET /auth/permissions`
- Logout endpoint: `POST /auth/logout`

Sessions are attached via bearer token or cookie.

## Environment variables

- `LMCP_ENV`
- `LMCP_PRODUCTION_MODE`
- `LMCP_DEPLOYMENT_PROFILE`
- `LMCP_AUTH_ALLOW_DEMO_USERS`
- `LMCP_AUTH_REQUIRED`
- `LMCP_CORS_ORIGINS`
- `LMCP_RATE_LIMIT_ENABLED`
- `LMCP_RATE_LIMIT_PER_MINUTE`
- `LMCP_OPERATOR_SESSION_COOKIE_SECURE`
- `LMCP_SECRET_KEY`

## Docker usage

- `docker compose up --build`
- Backend runs on port `8000`
- Frontend runs on port `4173` or behind nginx depending deployment choice

## Production safety

- Manual approval remains mandatory.
- `review_ready` remains mandatory.
- Proof capture remains mandatory.
- Final submission remains manual-only.
- Legacy routers remain disabled by default.

## Supervised-live deployment

The supervised-live profile keeps demo users disabled by default, enables auth, enables rate limiting, and preserves telemetry fallback for missing runtime data.

