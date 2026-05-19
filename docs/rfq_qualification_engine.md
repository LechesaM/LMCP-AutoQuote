# RFQ Qualification Engine

## Purpose
The RFQ Qualification Engine is an advisory gating layer that classifies RFQs, checks compliance signals, inspects submission method, evaluates viability, and recommends one of three outcomes:
- `GO`
- `MANUAL_REVIEW`
- `REJECT`

It does not submit work, approve work, or bypass governed workflow stages.

## Classification Rules
Classification categories:
- `consumables`
- `equipment_supply`
- `building_materials`
- `ppe`
- `household_products`
- `technical_fabrication`
- `construction_execution`
- `professional_services`
- `catering`
- `it_equipment`
- `fuel_diesel`
- `unknown`

Outcome rules:
- `catering` -> reject
- `medical consumables` -> reject
- `IT equipment` -> reject
- `petrol`, `diesel`, `fuel` -> reject
- `professional services` -> reject
- `construction execution` -> reject
- `technical fabrication` -> manual review
- `consumables`, `equipment_supply`, `building_materials`, `ppe`, `household_products` -> proceed if all other gates pass

## Compliance Detection
The engine detects compliance signals for:
- SBD4
- SBD8
- SBD6.1
- SBD9
- BBBEE
- CSD
- Tax PIN
- Director IDs
- Bank confirmation
- CIDB
- Local content
- Supplier code of conduct
- Company registration/CIPC
- SARS tax clearance
- Pricing schedule
- Quotation on company letterhead

Each item records:
- item name
- requirement status
- detected flag
- confidence
- source phrase
- blocker flag when missing a required item

## Submission Method Detection
Detected submission methods:
- `email`
- `portal`
- `physical_delivery`
- `courier_hand_delivery`
- `unknown`

Rules:
- email -> automation candidate, still manually reviewed
- portal -> supervised/manual
- physical/courier/dropbox -> manual-only
- unknown -> manual review

## Profitability Gates
The engine preserves the existing pricing thresholds:
- minimum profit: `R30,000`
- minimum supply margin: `25%`

Viability rules:
- margin below 25% -> `REJECT`
- estimated profit below R30,000 -> `REJECT`
- technical fabrication -> `MANUAL_REVIEW`
- physical submission -> `MANUAL_REVIEW` unless other safe signals exist
- missing critical fields -> `MANUAL_REVIEW`
- email plus clear supply classification plus compliant profitability -> `GO`

## Supplier Domain Mapping
Mapped domains:
- `household_products` -> FMCG wholesalers
- `consumables` -> FMCG/general wholesalers
- `equipment_supply` -> industrial/equipment suppliers
- `building_materials` -> hardware/building suppliers
- `technical_fabrication` -> fabrication specialists
- `ppe` -> PPE suppliers
- `fuel_diesel` -> excluded supplier domain
- `catering` -> excluded supplier domain
- `it_equipment` -> excluded supplier domain

## Recommendation Meanings
- `GO`: proceed as a strong candidate
- `MANUAL_REVIEW`: keep the RFQ in the governed review path
- `REJECT`: do not proceed

## Manual Review Triggers
- technical fabrication
- physical or courier submission
- unknown submission method
- missing required compliance signals
- missing critical RFQ fields

## Rejection Triggers
- excluded category
- margin below 25%
- estimated profit below R30,000
- construction execution
- catering
- IT equipment
- fuel or diesel
- professional services

## Dashboard and Reporting Integration
The dashboard and monitoring reports expose:
- qualification summary
- GO / MANUAL_REVIEW / REJECT counts
- risk breakdown
- supplier-domain breakdown
- submission-method breakdown

The summaries are advisory only and do not mutate workflow state.

## Final Rule
No autonomous final submission is enabled by this engine.
