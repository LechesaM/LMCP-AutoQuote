# P0 Remediation Acceptance Criteria

## GOV-003

- production readiness distinguishes declaration/configuration from exercised evidence;
- static defaults cannot alone produce operational GO;
- evidence includes provenance/status/timestamp or explicit reason unavailable;
- missing/stale/failed evidence blocks or degrades the relevant claim;
- human submission and production approval controls remain conservative.

## CAP-004

- placeholder values are explicitly non-production-ready;
- configured autoscaling and measured autoscaling are separate states;
- queue pressure and worker scaling evidence is reproducible;
- negative tests prove placeholders/stale evidence cannot produce certification.

## CI-005

- backend regressions are exercised on ordinary material PRs;
- frontend/library build checks remain;
- specialised production governance tests remain;
- no important backend path can routinely bypass all backend validation.

## SEC-006

- tracked production configuration is safe by design;
- repository history is inspected for secrets before assuming placeholder safety;
- any exposed/reused live credential is rotated;
- future secret introduction is harder and detectable.
