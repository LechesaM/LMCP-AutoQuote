# Validation Run 002 Report

Validation Run 002 completed against `validated-baseline-v1` (`f5cadbd`) with category-diversity coverage across 20 RFQs.

## Executive Summary

- RFQs processed: `20/20`
- Ready: `9`
- Not ready: `11`
- Manual interventions: `20`
- Average manual interventions per RFQ: `1.0`
- Supplier failures observed: `0`
- BOQ mapping failures observed: `0`
- Submission attempts performed: `0`
- Final evidence frozen on `2026-06-18`

## Approval Reason Distribution

1. `GOVERNANCE_REVIEW` - `13`
2. `COMPLIANCE_REVIEW` - `5`
3. `PRICING_REVIEW` - `2`

## Failure Distribution

1. `VALIDATION` - `6`
2. `DOCUMENT_GENERATION` - `2`
3. `PRICING` - `2`
4. `EXTRACTION` - `1`

## Validation Subgroups

- Metadata / completeness validation:
  - Missing closing date
  - Missing source/detail URL
  - Document-confidence blockers
- Qualification validation:
  - Briefing-session exclusion
- Technical validation:
  - Technical validation required before award

## Interpretation

- The supervised baseline remained repeatable for readiness on high-confidence fixtures.
- Validation/compliance and document-quality issues accounted for most non-readiness outcomes.
- Pricing remained a distinct business-rule failure.
- Supplier and BOQ mapping failures did not appear in the sampled evidence.

## Next Engineering Priorities

1. Validation and metadata completeness
2. Document-generation completeness
3. Extraction robustness
4. Pricing policy review

Supplier onboarding and BOQ mapping did not emerge as primary blockers in this run.
