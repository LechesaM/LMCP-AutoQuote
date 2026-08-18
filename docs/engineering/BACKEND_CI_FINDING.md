# CI Finding — Generic Backend Regression Coverage

The current generic `.github/workflows/ci.yml` builds the frontend and verifies AutoQuote libraries but does not run a broad backend pytest suite.

The separate production-governance workflow runs selected governance validators/tests only for governed path changes. This is useful but not equivalent to ordinary backend regression coverage on every material application PR.

CI-005 should add an appropriately partitioned backend regression job after the authoritative source state is synchronised and the current test/dependency requirements are re-audited.
