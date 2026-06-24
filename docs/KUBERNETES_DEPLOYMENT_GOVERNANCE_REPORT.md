# Kubernetes Deployment Governance Report

## Purpose
This report defines the governance rules for the Kubernetes package scaffold used by LMCP AutoQuote Phase 9D.1.

## Governing Rules
- The package is scaffold-only and not a live cluster deployment.
- Final automation remains disabled.
- Dry-run mode remains enabled.
- Human supervision remains mandatory.
- Submission locks are required.
- No embedded production credentials may appear in the package.

## Validation Coverage
The package validator checks:
- required manifest directories exist
- required workload manifests exist
- dry-run enforcement exists
- final automation is disabled
- supervision is mandatory
- no embedded credentials exist
- production overlay is separated from staging
- observability manifests exist
- storage placeholders exist
- network policy placeholders exist

## Package Boundaries
The Kubernetes package is split into:
- `k8s/base/` for reusable placeholders
- `k8s/overlays/staging/` for staging-safe values
- `k8s/overlays/production/` for locked production-safe values

## Production Overlay Controls
The production overlay must preserve:
- `LMCP_ALLOW_FINAL_AUTOMATION=false`
- `LMCP_DRY_RUN_MODE=true`
- `LMCP_REQUIRE_HUMAN_SUPERVISION=true`
- submission lock enforcement
- placeholder-only secrets

## Operational Requirement
This package is a governance and topology scaffold. It documents the future distributed production shape without authorizing deployment to a live Kubernetes cluster.
