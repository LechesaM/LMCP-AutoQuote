# Supplier and Pricing Intelligence

## Purpose
This library defines the non-runtime information model for supplier intelligence, product cataloging, historical pricing, lead times, preferred wholesalers, and provincial coverage.

## Governance Boundaries
- Advisory only.
- No live supplier API calls.
- No automated supplier negotiation.
- No bypass of manual approval or proof capture.

## Core Data Sets

### Supplier Register
Track supplier records with:
- supplier name
- category coverage
- province coverage
- city or depot coverage
- contact details
- quote contact person
- lead-time profile
- delivery profile
- preferred wholesaler flag
- evidence source
- reliability notes
- last verified date

### Product Catalog
Track catalog records with:
- category
- product name
- unit of measure
- approved supplier list
- standard pack size
- alternate brands
- stock notes
- delivery notes
- price band
- margin floor
- evidence notes

### Historical Pricing Register
Track pricing evidence with:
- product name
- supplier name
- quote reference
- quote date
- validity period
- quoted unit price
- quoted total
- VAT treatment
- delivery assumptions
- stock notes
- source type
- confidence level

### Lead Time Register
Track operational timing with:
- product or category
- supplier name
- standard lead time
- urgent lead time
- province impact
- stock dependency
- delivery complexity
- notes on seasonal variation

### Preferred Wholesaler Register
Track preferred sources with:
- supplier name
- category fit
- price consistency
- delivery reliability
- province coverage
- evidence quality
- last review date
- status: preferred, approved, conditional, or avoid

### Provincial Coverage Register
Track coverage by province:
- Gauteng
- Western Cape
- KwaZulu-Natal
- Eastern Cape
- Free State
- Limpopo
- Mpumalanga
- North West
- Northern Cape

Coverage status options:
- active
- partial
- unverified
- avoid

## Starter Supplier Segments
The initial supplier intelligence program should prioritize:
- office furniture suppliers
- PPE suppliers
- electrical suppliers
- construction material suppliers
- cleaning chemical suppliers
- stationery suppliers
- hardware and tools suppliers
- packaging suppliers
- janitorial consumables suppliers

## Recommended Evidence Fields
Each supplier or price record should ideally capture:
- source document or email reference
- operator who verified it
- date captured
- expiry or review date
- notes on freight or delivery
- notes on exclusions or limitations
- confidence rating

## Quality Rules
- Prefer direct supplier quotes over estimated prices.
- Treat stale pricing as advisory only.
- Separate supplier coverage from product coverage.
- Record missing fields instead of inventing them.
- Keep all records audit-friendly and append-only in spirit.

## Future Data Model Direction
This library can later be promoted into structured tables or seeded datasets, but only after governance approval.

## Current Expansion Reference
The current maturity snapshot and next expansion wave sequence are tracked in [AutoQuote Intelligence Maturity and Expansion Plan](./autoquote_intelligence_maturity_and_expansion_plan.md).
