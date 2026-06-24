# Phase 10.2 Supplier Intelligence & Risk Engine

## Purpose

Phase 10.2 adds supplier-side intelligence for supervised procurement decisioning. The goal is to score supplier fit, delivery risk, compliance readiness, pricing reliability, and historical suitability without enabling autonomous supplier selection.

## Read-Only Scope

This layer is strictly analytical:

- read-only
- staging-only
- dry-run enforced
- human supervision mandatory
- no supplier award authority
- no autonomous supplier selection
- no live supplier notifications
- no production procurement action

## Signals Tracked

- supplier fit score
- delivery risk score
- compliance readiness
- pricing reliability
- geographic suitability
- capacity suitability
- supplier document readiness
- supplier risk flags
- recommended supplier tier
- unresolved supplier blockers
- supplier intelligence history

## Safety Boundary

The engine is a decision-support layer only. It does not send live supplier notices, authorize awards, or move procurement action into production.

## Validation

Run:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile \
app/services/supplier_intelligence_service.py \
app/services/supplier_risk_scoring_service.py \
app/services/supplier_fit_scoring_service.py \
app/services/supplier_compliance_readiness_service.py \
tests/test_supplier_intelligence_service.py \
tests/test_supplier_risk_scoring_service.py \
tests/test_supplier_fit_scoring_service.py \
tests/test_supplier_compliance_readiness_service.py \
tests/test_supplier_intelligence_api.py

./.venv/bin/python -m pytest \
tests/test_supplier_intelligence_service.py \
tests/test_supplier_risk_scoring_service.py \
tests/test_supplier_fit_scoring_service.py \
tests/test_supplier_compliance_readiness_service.py \
tests/test_supplier_intelligence_api.py \
tests/test_main_runtime_surface.py

cd etenders_acquisition/lmcp-dashboard && npm run build
```

