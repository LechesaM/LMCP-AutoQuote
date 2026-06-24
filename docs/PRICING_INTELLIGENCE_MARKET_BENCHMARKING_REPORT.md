# Pricing Intelligence & Market Benchmarking Governance

Phase 10.4 provides a read-only, staging-only, supervision-gated pricing intelligence layer.

## Scope

- pricing benchmark readiness
- market rate comparison readiness
- historical pricing reference readiness
- supplier quote comparison readiness
- margin scenario readiness
- pricing confidence score
- abnormal price variance indicators
- underpricing risk indicators
- overpricing competitiveness indicators
- VAT and markup visibility
- escalation-required pricing items
- mandatory human price approval
- pricing intelligence history

## Safety Model

- pricing intelligence is advisory only
- all final prices require human approval
- no automatic tender submission
- no live supplier purchase orders
- no procurement commitment generation
- dry-run enforced
- supervision mandatory
- read-only governance surface
- staging-only execution posture
- no live supplier, banking, ERP, or procurement credentials

## Validation

- `PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile app/services/pricing_intelligence_governance_service.py app/services/market_benchmarking_service.py app/services/pricing_confidence_service.py app/services/margin_scenario_service.py tests/test_pricing_intelligence_governance_service.py tests/test_market_benchmarking_service.py tests/test_pricing_confidence_service.py tests/test_margin_scenario_service.py tests/test_pricing_intelligence_api.py`
- `./.venv/bin/python -m pytest tests/test_pricing_intelligence_governance_service.py tests/test_market_benchmarking_service.py tests/test_pricing_confidence_service.py tests/test_margin_scenario_service.py tests/test_pricing_intelligence_api.py tests/test_main_runtime_surface.py`
- `cd etenders_acquisition/lmcp-dashboard && npm run build`
