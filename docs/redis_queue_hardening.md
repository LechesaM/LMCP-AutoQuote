# Redis Queue Hardening

## Overview
LMCP queue durability is prepared for Redis while retaining the local durable queue as a fallback.

## Queue Backend Policy
- `local` is allowed for development and supervised-live fallback.
- `redis` is preferred when a queue service is available.
- Production warns when the local queue backend is active.

## Durability Rules
- Jobs are acknowledged explicitly.
- Failed jobs can retry only within the retry policy.
- Dead-letter handling is append-only and reviewable.

## Recovery
- Queue recovery emits recommendations only.
- Worker supervision tracks stale heartbeats and queue lag.
- No autonomous recovery loop is introduced.
