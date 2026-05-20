# Supervised-Live Stabilization

## Purpose

This layer hardens LMCP for sustained supervised-live operation without changing procurement governance.

## What it monitors

- Runtime degradation
- Queue instability
- Fallback resilience
- Telemetry noise
- Governance consistency
- Operator fatigue
- Deployment stability

## Operating principles

- Read-only visibility first
- Dry-run cleanup by default
- Manual confirmation for any cleanup review
- No autonomous procurement execution
- No bypass of `review_ready` or proof capture

