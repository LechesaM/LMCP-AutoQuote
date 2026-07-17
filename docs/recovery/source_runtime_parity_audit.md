# Source/Runtime Parity Audit

Audit date: 2026-07-16
Branch: recovery/rfq-quote-pack-bridge
Commit: c02c0d56
External evidence directory: `/Users/Shared/LMCP-Recovery-2026-07-15/source-runtime-parity`

## Safety Constraints Followed

- No Docker restart, stop, recreate, rebuild, pull, or signal command was run.
- Docker usage was limited to read-only `docker inspect` and `docker exec`.
- No POST, PUT, PATCH, or DELETE endpoints were invoked.
- Runtime stores, PostgreSQL, Redis, Docker volumes, RFQ data, quote packs, submission packs, proofs, and harvested documents were not modified.
- Source was not modified until running runtime identity, checksums, health, and OpenAPI evidence were captured externally.

## Captured Running Runtime Identity

Evidence files:

- `docker-inspect-lmcp-api.json`
- `container-process-and-files.txt`
- `running-health.json`
- `running-openapi.json`

Running container identity:

| Field | Evidence |
| --- | --- |
| Container | `lmcp-api` |
| Container id | `af60415ab2a9767975bb0e4adc471cc1eeac14d7aa59f61cc2f40dde8e773f89` |
| Image | `lmcp-autoquote-server-api` |
| Image id | `sha256:747db50345468c8b01081e9a5fc047af2160f8455d76716b59c109b63efe3b9f` |
| Created | `2026-07-08T19:01:58.944692302Z` |
| Started | `2026-07-08T19:02:04.970104013Z` |
| Command | `uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| Working directory | `/app` |
| Container Python | `Python 3.12.13` |
| Host audit Python | `.venv` Python 3.9 |

Mounts:

| Source | Destination | Type |
| --- | --- | --- |
| `/Users/Shared/LMCP-AutoQuote-Server` | `/app` | bind |
| `/Users/Shared/LMCP-AutoQuote-Server/runtime` | `/app/runtime` | bind |
| `/Users/Shared/LMCP-AutoQuote-Server/monthly_quotes` | `/app/monthly_quotes` | bind |

## Host/Container Source Parity

The mounted container files match the host files by checksum for the checked samples:

| File | SHA-256 |
| --- | --- |
| `app/main.py` | `7ac69d2b151aef3862079f3457eccf2f044f9794c4703886128b8b5f76c238f9` |
| `app/api/rfq_lifecycle_api.py` | `ec4ff3dbcc55ba48021db231ace8a96fe41a022ed719c34bab76c1907017a78d` before patch |
| `app/services/rfq_lifecycle_service.py` | `7b2fbe9285b356bf66d7ecd215ec66426bcab08e23bf59490462230832a1f6c1` |
| `app/api/smart_harvester_v31_api.py` | `8fb51e7f54900f5b2be2f6d26d8a4e311685ea1e2ef4a47ef343ab92adeabab9` |
| `app/api/real_rfq_harvester_v32_api.py` | `00db8fff928e719b432f43cf5c260b7298424d4de98c38149c0ba60b1c65e717` |
| `app/api/tender_form_intelligence_api.py` | `a5bce60b36dd574df8c9a857976e2d38d10a3fcca52245689a162212c0ffae71` |
| `app/api/sbd_intelligence_api.py` | `56b39ec44e84a50c7e0eae2e9087915730744307fafff7d867d7a83059eeaa89` |

However, `app/main.py` in the bind mount was modified at `2026-07-08T20:26:29Z`, after the running process started at `2026-07-08T19:02:04Z`. The running process therefore predates the current mounted source.

## Version Definitions

| Version string | Host source file | Container source file | Used by endpoint/process | Checksum match | Likely status |
| --- | --- | --- | --- | --- | --- |
| `2.6.0-manual-production` | Not found in current mounted source sample | Not found in current mounted source sample | Reported by running `/health` and running OpenAPI capture | Not applicable | Active only in running process memory from pre-recovery source |
| `2.5.3-v50.7-etenders-promotion-gate` | `app/main.py:39` | `/app/app/main.py:39` | Used by direct source import | Yes | Active in checked-out source; not loaded by current running process |

Root cause: the API container bind-mounts the repository, but PID 1 imported `app.main` before the current recovered source was written to the bind mount. Python does not reload already imported modules merely because bind-mounted files changed. The 2.6.0 health/version is therefore process-memory state, while the checked-out source is 2.5.3.

## Router Parity

Before the patch, direct source import under Python 3.9 reported:

- Source version: `2.5.3-v50.7-etenders-promotion-gate`
- Loaded routers: 95
- Failed routers: 15
- Route objects: 402

The running API reported:

- Runtime version: `2.6.0-manual-production`
- OpenAPI paths: 351
- Container process Python: 3.12.13

The router count mismatch is not a simple source/container file mismatch. It is a combination of:

1. running process loaded older source before the bind-mounted files changed;
2. current source is being imported under host Python 3.9 while the container uses Python 3.12;
3. host import is outside the container path context expected by several optional acquisition routers that touch `/app` during import.

## Minimal Patch Applied

Only the high-confidence Python 3.9 compatibility defect was patched:

- `app/api/rfq_lifecycle_api.py`
  - changed `payload: dict | None = None` to `payload: Optional[Dict[str, Any]] = None`
  - added an explicit `Dict[str, Any]` return annotation

No runtime-store behavior, frontend code, router registry behavior, Docker configuration, or submission behavior was changed.

## Open Issues

- Fourteen optional acquisition/intelligence routers still fail direct host import when the host process cannot access `/app`.
- The running process is healthy but stale relative to current source.
- A controlled restart should only be considered after operator review of the route parity report and this audit.
