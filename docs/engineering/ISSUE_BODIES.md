# Work Queue Issue Bodies

This file is a durable source for the work-package descriptions used to create/track GitHub issues. If GitHub issue metadata diverges from the approved work queue, update both intentionally.

## SYNC-001

Synchronise the authoritative August local checkout to a non-destructive GitHub branch. Do not force-push or overwrite `release/v1.1`. Preserve uncommitted work, inspect divergence, audit secret-sensitive paths, push `sync/authoritative-2026-08-18`, and open a draft reconciliation PR.

## AUDIT-002

After SYNC-001, rerun the Phase 65 implementation/evidence audit against the synchronised branch. Classify capabilities as implemented, partial, scaffold, placeholder-risk, absent, or superseded. Produce the exact closure path and do not reopen previously closed work without evidence.

## GOV-003

Replace synthetic/static production-readiness declarations with evidence-backed gates where empirical proof is required. Preserve conservative human-control and procurement safety boundaries.

## CAP-004

Separate autoscaling configuration readiness from exercised autoscaling capability. Placeholder strings/manifests cannot satisfy production readiness. Require measured queue/worker/scaling evidence for production claims.

## CI-005

Expand ordinary pull-request CI so material backend changes receive backend regression validation in addition to existing frontend and specialised governance checks.

## SEC-006

Reconcile tracked production environment files and repository secret hygiene. Inspect history before deleting anything; rotate any credential that was live or reused; prevent future secret commits where practical.

## HA-007

Revalidate HA topology, distributed sessions, database failover, Redis/cache/broker and queue/worker behaviour against real infrastructure and controlled failure scenarios.

## LOAD-008

Build a reproducible capacity/concurrency certification harness using realistic procurement workloads and measured latency, error, throughput, queue, database and resource evidence. Report only the envelope actually proven.

## REVIEW-009

Adopt a recurring independent second-agent, read-only-first review gate for material backend, security, workflow, compliance, data and production changes.

## FACTORY-010

Configure GitHub branch/ruleset protections so release governance is enforceable: required checks, human/code-owner review, protection against force pushes/deletion, and controlled merge authority.
