# Phase 11.3 Tender Knowledge Graph & Relationship Intelligence

This release adds a supervised, read-only knowledge graph layer that maps tenders, suppliers, departments, commodities, BOQ items, pricing benchmarks, outcomes, risks, compliance signals, and executive decisions.

## Safety Model

- Read-only governance surface
- Staging-only execution posture
- Dry-run enforced
- Human supervision mandatory
- Supervised relationship review required
- Graph governance review required
- No autonomous procurement decisions
- No autonomous supplier ranking changes
- No autonomous pricing overrides
- No autonomous strategy modifications
- No production graph learning execution
- No live graph database credentials

## Validation

```bash
PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile \
  app/services/tender_knowledge_graph_service.py \
  app/services/entity_relationship_mapping_service.py \
  app/services/procurement_entity_resolution_service.py \
  app/services/commodity_relationship_service.py \
  app/services/risk_relationship_intelligence_service.py \
  tests/test_tender_knowledge_graph_service.py \
  tests/test_entity_relationship_mapping_service.py \
  tests/test_procurement_entity_resolution_service.py \
  tests/test_commodity_relationship_service.py \
  tests/test_risk_relationship_intelligence_service.py \
  tests/test_tender_knowledge_graph_api.py

./.venv/bin/python -m pytest \
  tests/test_tender_knowledge_graph_service.py \
  tests/test_entity_relationship_mapping_service.py \
  tests/test_procurement_entity_resolution_service.py \
  tests/test_commodity_relationship_service.py \
  tests/test_risk_relationship_intelligence_service.py \
  tests/test_tender_knowledge_graph_api.py \
  tests/test_main_runtime_surface.py

cd etenders_acquisition/lmcp-dashboard && npm run build
```

