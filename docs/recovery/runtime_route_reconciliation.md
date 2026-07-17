# Runtime Route Reconciliation

Audit date: 2026-07-16
Branch: recovery/rfq-quote-pack-bridge
Commit: c02c0d56
Evidence folder: `/Users/Shared/LMCP-Recovery-2026-07-15/route-reconciliation`

## Safety

This reconciliation used in-process OpenAPI generation, captured running OpenAPI artifacts, source inspection, Git history search, JSON comparison, Python compile checks, and focused tests. Docker was not restarted, stopped, rebuilt, recreated, or signalled. No runtime store, Live RFQ Store, PostgreSQL, Redis, harvested document, quote pack, submission pack, proof, or monthly quote data was modified. No POST, PUT, PATCH, or DELETE endpoint was invoked.

Live GET probes to `localhost:8000` were attempted but failed to connect from this environment, so route comparison uses the previously captured running OpenAPI snapshot.

## Route Sets

| Route set | Source | Paths | Method/path pairs | Loaded routers | Failed routers | Duplicate route pairs |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Running API | `after-import-safety/running-openapi.json` | 351 | 359 | 67 | 0 | 0 |
| Current source final controlled baseline | `final-baseline/source-openapi.json` | 295 | 303 | 54 | 0 | 0 |

## Difference Summary

| Classification | Count | Meaning |
| --- | ---: | --- |
| PRESENT_IN_BOTH | 300 | Method/path and basic OpenAPI metadata are present in both. |
| SAME_ROUTE_DIFFERENT_OPERATION | 3 | Same method/path, changed operation ID. |
| CONDITIONAL_REGISTRATION | 52 | Running routes intentionally not exposed by the final controlled source baseline unless explicitly enabled or restored. |
| PROCESS_MEMORY_ONLY | 4 | Historical dashboard/go-live routes present only in the stale running process and historical evidence. |
| SOURCE_ONLY | 0 | No source-only method/path pairs are exposed by default. |

The full per-route classification is in `docs/recovery/runtime_route_difference_matrix.json`.

## SBD Ownership Resolution

Duplicate source routes were eliminated:

- `GET /sbd-intelligence/status`
- `POST /sbd-intelligence/complete`

Canonical owner is `app.api.sbd_intelligence_api`. The tender-form facade `app.api.tender_form_intelligence_api` now owns `/tender-form-intelligence/*`, which also resolves six formerly running-only tender-form routes.

Evidence: `docs/recovery/sbd_route_ownership_matrix.md`.

## Remaining Running-Only Routes

The original 10 running-only compatibility routes are dispositioned in `docs/recovery/final_running_route_disposition.md`.

RFQ lifecycle manual-pricing and validation compatibility routes are now present in source OpenAPI with matching operation IDs. Remaining running-only concerns are autonomous legacy health/run-sync, dashboard manual-review, go-live, `/health/workflows`, and `/system/control/effective-status`.

## Source-Only Routes

One hundred twenty-six source-only method/path pairs from the prior ungated source are now controlled by the operational baseline. Under default startup, source-only exposed method/path pairs are reduced to 0.

Key restart concern: 114 source-only routes are risky acquisition, browser, upload, submission, autonomous, document-processing, pricing, or RFQ-processing routes. These should not become active silently.

## Autonomous Metadata Review

Three `/autonomous` method/path pairs are present in both route sets but have changed operation IDs:

- `GET /autonomous/last-result`
- `GET /autonomous/status`
- `POST /autonomous/run-once`

This is metadata drift rather than a path-level break. Source default autonomous state is now disabled in both `app.autonomous_api` and `app.api.autonomous_api`; focused tests assert that default.

## Conclusion

The duplicate SBD route defect is fixed. Source import reproducibility is fixed. RFQ lifecycle/manual-pricing compatibility is restored. Health/control compatibility is restored. High-risk source-only families are disabled before import. Restart is classified as `SAFE_TO_RESTART_WITH_KNOWN_ROUTE_CHANGES`, pending operator acceptance of the documented route waivers and pre-restart evidence capture.
