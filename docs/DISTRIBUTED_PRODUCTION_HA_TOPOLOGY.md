# Distributed Production HA Topology

## Scope
This document defines a Kubernetes-ready high-availability scaffold for the future distributed production topology of LMCP AutoQuote. It is intentionally non-deploying, staging-safe, and supervision-bound.

## Topology Intent
The package separates the runtime into independently reviewable planes:
- application plane for backend and frontend services
- worker plane for queue processing
- data plane for Redis and PostgreSQL placeholders
- observability plane for Prometheus and Grafana placeholders
- policy plane for config, secrets placeholders, network policy, and submission-lock enforcement

## Failure Domains
The scaffold assumes the following failure boundaries:
- application replicas can be restarted without changing the data plane
- worker pods can be scaled separately from the UI and API
- Redis and PostgreSQL remain isolated from application workloads
- observability components are read-only by design
- network policy exists as a control point, not as an execution bypass

## Safety Boundary
The topology does not:
- enable autonomous live submissions
- add real production credentials
- deploy to a live Kubernetes cluster
- weaken supervision boundaries
- bypass submission locks

Human supervision remains mandatory. Dry-run mode remains enabled.

## Kubernetes Package
The scaffold is organized as:
- `k8s/base/`
- `k8s/overlays/staging/`
- `k8s/overlays/production/`

The production overlay preserves:
- `LMCP_ALLOW_FINAL_AUTOMATION=false`
- `LMCP_DRY_RUN_MODE=true`
- `LMCP_REQUIRE_HUMAN_SUPERVISION=true`
- submission locks required
- no embedded production credentials

## Operational Shape
The intended future shape is:
- backend deployment and service
- frontend deployment and service
- worker deployment
- Redis deployment and service placeholder
- PostgreSQL statefulset and service placeholder
- Prometheus deployment and service placeholder
- Grafana deployment and service placeholder
- configmaps
- secrets placeholders only
- network policy placeholders
- persistent volume claim placeholders

## Validation Posture
The Kubernetes package is validated as a governance artifact before any cluster deployment is contemplated. Validation must fail if any safety control drifts from the locked defaults.
