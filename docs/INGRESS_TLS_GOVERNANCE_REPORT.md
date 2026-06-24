# Ingress and TLS Governance Report

This report defines the staged ingress governance scaffold for LMCP AutoQuote. It is read-only, staging-only, supervision-gated, and dry-run enforced.

## Scope

The package tracks:

- TLS readiness
- ingress isolation readiness
- internal versus external routing segregation
- certificate governance readiness
- API exposure governance
- observability ingress governance
- administrative access isolation
- public attack-surface indicators
- ingress degradation indicators
- ingress governance history

## Safety boundary

The scaffold does not enable public exposure, live DNS, or live certificates. Production remains under the same control boundary used by the rest of the staged governance package:

- final automation stays disabled
- dry-run mode stays enabled
- human supervision stays mandatory
- submission locks remain required

## Kubernetes placeholders

The base package includes placeholders for:

- `ingress.yaml`
- `tls-secret-placeholder.yaml`
- `cert-manager-placeholder.yaml`

These files are intentional placeholders only. They are not production-ready ingress or certificate assets.

## Governance model

The ingress governance service resolves three explicit recovery states:

- `recovered`
- `degraded-but-recovering`
- `unresolved-blocked`

The state is derived from the staged ingress manifests and the safety boundary checks. Unresolved blockers are never hidden and remain visible in the evidence payload and Command Centre view.

## Evidence outputs

The runtime evidence includes:

- `recovery_state`
- `recovery_state_history`
- `unresolved_blockers`
- `recovery_rationale`
- `blocker_sources`

The dashboard panel and API expose the same data so the staged package can be reviewed without any live authority.
