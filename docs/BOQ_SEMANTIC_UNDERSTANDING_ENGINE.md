# BOQ Semantic Understanding Engine

Phase 10.3 introduces a read-only, staging-only BOQ semantic understanding layer for LMCP AutoQuote.

## Scope

- BOQ item classification readiness
- trade/package mapping readiness
- unit-of-measure normalization readiness
- quantity interpretation readiness
- measurement risk scoring
- ambiguous item detection
- missing specification detection
- pricing preparation readiness
- unresolved BOQ semantic blockers
- BOQ semantic history

## Safety Model

- read-only
- staging-only
- dry-run enforced
- human supervision mandatory
- no autonomous pricing submission
- no live procurement action
- no supplier award authority
- no production tender submission

## Validation

- `PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile app/services/boq_semantic_understanding_service.py app/services/boq_item_classification_service.py app/services/boq_measurement_risk_service.py app/services/boq_trade_mapping_service.py app/services/boq_ambiguity_detection_service.py tests/test_boq_semantic_understanding_service.py tests/test_boq_item_classification_service.py tests/test_boq_measurement_risk_service.py tests/test_boq_trade_mapping_service.py tests/test_boq_ambiguity_detection_service.py tests/test_boq_semantic_understanding_api.py`
- `./.venv/bin/python -m pytest tests/test_boq_semantic_understanding_service.py tests/test_boq_item_classification_service.py tests/test_boq_measurement_risk_service.py tests/test_boq_trade_mapping_service.py tests/test_boq_ambiguity_detection_service.py tests/test_boq_semantic_understanding_api.py tests/test_main_runtime_surface.py`
- `cd etenders_acquisition/lmcp-dashboard && npm run build`
