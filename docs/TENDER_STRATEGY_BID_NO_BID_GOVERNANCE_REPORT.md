# Phase 10.5 Tender Strategy & Bid/No-Bid Governance

This phase adds a read-only, staging-only governance layer for tender strategy and bid/no-bid decision support.

## Scope

- Advisory-only tender strategy analysis
- Human-approved bid/no-bid decision support
- Executive review for high-risk tenders
- Deterministic governance snapshots with latest and history views

## Readiness Signals

- Bid/no-bid readiness
- Tender attractiveness score
- Win probability estimate
- Strategic fit score
- Pricing competitiveness alignment
- Supplier readiness alignment
- Compliance readiness alignment
- Risk-adjusted opportunity score
- Mandatory document readiness
- Submission urgency indicators
- Executive review required
- Recommendation degradation indicators
- Unresolved strategy blockers
- Tender strategy governance history

## Safety Boundaries

- Read-only governance surface
- Staging-only execution posture
- Dry-run enforced
- Human supervision mandatory
- Bid/no-bid human approval required
- Executive review required for high-risk tenders
- No autonomous tender submission
- No production submission authority
- No procurement commitment generation
- No live tender portal credentials

## Validation

```bash
PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile \
  app/services/tender_strategy_governance_service.py \
  app/services/bid_no_bid_scoring_service.py \
  app/services/tender_win_probability_service.py \
  app/services/tender_strategy_risk_service.py \
  tests/test_tender_strategy_governance_service.py \
  tests/test_bid_no_bid_scoring_service.py \
  tests/test_tender_win_probability_service.py \
  tests/test_tender_strategy_risk_service.py \
  tests/test_tender_strategy_governance_api.py

./.venv/bin/python -m pytest \
  tests/test_tender_strategy_governance_service.py \
  tests/test_bid_no_bid_scoring_service.py \
  tests/test_tender_win_probability_service.py \
  tests/test_tender_strategy_risk_service.py \
  tests/test_tender_strategy_governance_api.py \
  tests/test_main_runtime_surface.py

cd etenders_acquisition/lmcp-dashboard && npm run build
```
