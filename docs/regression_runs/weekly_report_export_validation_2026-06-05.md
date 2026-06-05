# Weekly Report Export Validation - 2026-06-05

## Change Summary
The active shared-repo frontend now includes a Weekly Report workspace in the command-centre sidebar. The weekly AutoQuote report export reads from page state, including editable category wave counters, so the rendered report and downloaded markdown stay aligned.

## Validation Scope
- UI surface: Command Centre sidebar workspace `Weekly Report`
- Export action: weekly markdown download
- Sidebar navigation: enabled in `frontend/src/App.jsx`
- Frontend component: `frontend/src/components/WeeklyIntelligenceReportWorkspace.jsx`
- Export state source: local page state for wave/category counters
- Backend health and operator auth endpoint reachability
- Controlled proof and controlled proof report

## Validation Status
Current validation is good.

Validated successfully:
- `curl http://127.0.0.1:8000/health`
- `curl http://127.0.0.1:5173`
- `curl http://127.0.0.1:8000/operator-auth/session`
- `curl -X POST http://127.0.0.1:8000/operator-auth/login` with an invalid validation-only password returned the expected `401`
- `cd frontend && npm run build`
- `make controlled-proof`
- `make controlled-proof-report`

Not applicable in this shared frontend:
- `npm run check:autoquote-libraries` is not defined in `frontend/package.json`

Controlled proof results:
- Controlled status: `controlled`
- Workflow checks passed: `7 / 7`
- Quote pack surface: passed
- Pricing surface: passed
- Submission surface: passed
- Portal upload: blocked
- Email send: blocked
- Final submit: blocked
- Loaded routers: `67`
- Failed routers: `0`
- Duplicate routes: `0`

Report note:
- `make controlled-proof-report` now prints successfully from `/private/tmp/lmcp_runtime/logs/controlled_runtime_proof.json`.

## Decision
APPROVED - Weekly report export now reads from page state; controlled proof unchanged.

## Next Step
Keep the repo frozen after this controlled UI/export validation and proceed to Weekly Regression Run #2.

## Notes
This record captures the controlled UI/export validation triggered by the weekly report export behavior change.
