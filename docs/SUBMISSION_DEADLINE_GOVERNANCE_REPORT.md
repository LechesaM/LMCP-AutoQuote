# Submission Deadline Governance Report

## Scope
This surface provides read-only staging governance for submission cutoff tracking, upload-window governance, courier timing, portal timeout, escalation timing, and late-submission prevention.

## Runtime Surface
- Backend service: `app.services.deadline_governance_service.DeadlineGovernanceService`
- Read-only routes:
  - `GET /rfq-lifecycle/deadline-governance`
  - `GET /rfq-lifecycle/deadline-governance/latest`
  - `GET /rfq-lifecycle/deadline-governance/history`
- Command Centre panel: `Submission Deadline Governance`

## Governance Coverage
The surface classifies and scores:
- submission cutoff tracking
- upload-window governance
- courier timing governance
- portal timeout governance
- escalation timing governance
- late-submission prevention tracking

It also reports:
- deadline-risk warnings
- overdue-submission indicators
- congestion-window indicators
- timing-readiness scoring
- submission-deadline governance history

## Safety Constraints
- Staging-only, read-only visibility
- No autonomous live submissions
- No irreversible actions
- No production connectivity required
- Dry-run protections remain authoritative

## Verification Expectations
- `py_compile` must succeed for the service, API, and runtime surface tests
- `pytest` must pass for the deadline governance service and API tests
- The frontend build must continue to pass
- The readiness declaration surface must continue to load
