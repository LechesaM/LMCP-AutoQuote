# Harvest Source Expansion

This package implements governed tiered source harvesting.

Rules:
- Tier 1 and Tier 2 are the only active harvesting tiers by default.
- Tier 3 is limited and scheduled more conservatively.
- Tier 4 is passive discovery only and cannot be directly harvested into workflow.
- Harvested items always pass through the RFQ Qualification Engine before promotion.
- No quote generation or submission is triggered from harvesting.

Operator review capacity:
- 10 operators
- 100 RFQs per operator per day
- 1,000 RFQs total review capacity per day

The package is advisory and governed. It does not bypass manual approval, review_ready, proof capture, or submission controls.
