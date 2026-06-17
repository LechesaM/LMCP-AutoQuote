# Technical Debt Register

## Purpose
This register records non-blocking technical debt for future release planning only.

## Current Items
- Pydantic `orm_mode` warning cleanup
- future dependency upgrades
- performance improvements in high-volume paths
- logging enhancements for review traceability
- additional metrics normalization work
- test suite hardening for edge-case RFQs
- AutoQuote library generator may fail with `EPERM` when updating docs bundle outputs; current workaround is manual sync plus drift verification, and future improvement is atomic writes or preflight permission checks

## Debt Handling Rules
- Document only unless a release explicitly schedules the fix.
- Do not bundle technical debt cleanup into workflow changes without review.
- Keep runtime stability ahead of refactoring convenience.

## Suggested Prioritization
1. Warnings that affect developer confidence or test noise.
2. Performance issues in repeated read paths.
3. Logging and observability improvements.
4. Dependency upgrades with low regression risk.
5. Larger refactors that need dedicated planning.

## Tracking Fields
Each debt item should record:
- title
- impact
- scope
- estimated effort
- risk
- owner
- target release
- status
