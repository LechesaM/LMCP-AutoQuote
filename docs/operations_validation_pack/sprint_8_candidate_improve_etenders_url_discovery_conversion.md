# Sprint 8 Candidate: Improve eTenders URL Discovery Conversion

## Status

- Type: Backlog item
- Sprint: Future engineering sprint
- Current state: Not implemented
- Sprint 7 impact: None

## Problem Statement

eTenders opportunities are being discovered and qualified, but a subset of document candidates are not progressing into document acquisition because `detail_url` and `document_url` are not being persisted consistently.

Observed current conversion:

- `acquisition_document_links_detected / document_candidate_total`
- Current: `25%`
- Target: `50%+`

## Objective

Improve the conversion of eTenders document candidates into acquisition-ready opportunities by increasing the rate at which usable `detail_url` and `document_url` values are discovered and persisted before `RFQ_DOCUMENT_ACQUISITION_ENGINE` runs.

## Success Metric

- `acquisition_document_links_detected / document_candidate_total`
- Target: `50%+`

## Expected Impact

- More document acquisition attempts with usable seed URLs
- More BOQ extraction opportunities
- More pricing schedule extraction opportunities
- More returnables extraction opportunities
- More submission-ready RFQs without changing source count

## Guardrails

- Do not change Sprint 7 governance.
- Do not change qualification rules.
- Do not change approval rules.
- Do not change submission logic.
- Do not enable autonomous submission.

## Evidence Basis

- Current pilot evidence indicates the main loss occurs between document candidate detection and usable URL discovery.
- The bottleneck is throughput-related, not governance-related.
- The backlog item exists only so the next engineering window has a clear target.
