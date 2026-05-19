# Tiered Harvest Source Expansion

## Tier Model

- Tier 1: 20 to 40 active sources, harvested every 1 to 3 hours
- Tier 2: 75 to 150 active sources, harvested daily
- Tier 3: 300 to 600 active sources, harvested weekly
- Tier 4: 1,000 to 5,000+ passive sources, discovery only

## Source Activation Policy

- Tier 1 maximum active sources: 40
- Tier 2 maximum active sources: 150
- Tier 3 maximum active sources: 600
- Tier 4 maximum active sources: 0 direct workflow sources
- Duplicate URLs are blocked during registry writes
- Tier 4 sources remain passive unless manually promoted under governed review

## Operator Capacity Model

- Operators: 10
- Max review capacity per operator per day: 100 RFQs
- Total review capacity per day: 1,000 RFQs
- The system never promotes more review items than capacity allows

## Qualification-First Pipeline

1. Harvest source payload
2. Parse and normalize listing
3. Apply pre-qualification filters
4. Send every harvested opportunity through the RFQ Qualification Engine
5. Apply promotion policy
6. Promote only within operator capacity

## Promotion Rules

- GO candidates are prioritized first
- High-confidence MANUAL_REVIEW items are next
- REJECT items are suppressed
- Low-confidence items remain passive unless manually promoted
- Tier 4 direct promotion is suppressed
- Harvesting never triggers quote generation directly

## Scaling

The registry supports 1,000 to 5,000+ sources by keeping most sources inactive by default, constraining active tiers, and using passive discovery for the long tail.

## Governance

- No autonomous final submission
- No bypass of manual approval
- No bypass of review_ready
- No bypass of proof capture
- No workflow bypass
