# Safe Test Inventory

Audit date: 2026-07-16
Branch: recovery/rfq-quote-pack-bridge
Scope: classify discovered tests for safe recovery validation without runtime-store mutation, email, portal upload, browser launch, or external side effects.

## Classifications

| Test file | Classification | Reason | Safe command |
| --- | --- | --- | --- |
| `tests/test_router_imports_python39.py` | SAFE_UNIT | Focused import/type-hint check for the RFQ lifecycle router compatibility fix. No HTTP calls and no Docker actions. | `PYTHONPYCACHEPREFIX=/tmp/lmcp_pycache .venv/bin/python -m pytest -q tests/test_router_imports_python39.py` |
| `app/api/test_pricing_api.py` | UNKNOWN | Filename matches test discovery but is an API module, not a pytest validation target. | Do not run directly during recovery. |
| `test_tender_pipeline_channels.py` | SAFE_UNIT for pytest collection only; RUNTIME_MUTATING if executed as a script | Main-guard execution can exercise pipeline behavior. Pytest collection is expected to collect little or no direct tests. | Not used for this recovery gate. |
| `test_sbd_auto_detection.py` | RUNTIME_MUTATING | Exercises document/form processing paths with runtime artifacts. | Prohibited in this audit. |
| `test_sbd_version_detector.py` | RUNTIME_MUTATING | Exercises detector behavior against document/runtime inputs. | Prohibited in this audit. |
| `test_auto_multi_form_pipeline.py` | RUNTIME_MUTATING | Exercises form pipeline behavior and generated artifacts. | Prohibited in this audit. |
| `test_signatures.py` | RUNTIME_MUTATING | Signature artifact behavior can write generated files. | Prohibited in this audit. |
| `test_stamp_integration.py` | RUNTIME_MUTATING | Stamp/signature integration can write generated files. | Prohibited in this audit. |
| `test_direct_signature.py` | RUNTIME_MUTATING | Direct signature artifact flow can write outputs. | Prohibited in this audit. |
| `test_form_filler.py` | RUNTIME_MUTATING | Form filler execution can generate completed files. | Prohibited in this audit. |
| `test_live_email.py` | EMAIL_OR_PORTAL; COLLECTION_SIDE_EFFECT | Contains live email/submission-oriented execution settings and should not be collected or run in recovery. | Prohibited in this audit. |
| `test_pipeline.py` | EMAIL_OR_PORTAL; COLLECTION_SIDE_EFFECT | Pipeline test includes email/portal-style payloads and import-time execution risk. | Prohibited in this audit. |
| `test_mbd4_profile.py` | RUNTIME_MUTATING | Exercises buyer form/profile generation behavior. | Prohibited in this audit. |
| `test_tender_submission_pipeline.py` | RUNTIME_MUTATING; OPENS_BROWSER | Creates tender pack artifacts and can open Preview. | Prohibited in this audit. |
| `test_live_submission_email.py` | EMAIL_OR_PORTAL; COLLECTION_SIDE_EFFECT | Live submission email behavior is outside safe read-only validation. | Prohibited in this audit. |
| `test_tender_form_priority_engine.py` | RUNTIME_MUTATING | Exercises form priority pipeline behavior. | Prohibited in this audit. |
| `test_pipeline_with_buyer_docs.py` | RUNTIME_MUTATING | Exercises pipeline with buyer documents and generated artifacts. | Prohibited in this audit. |

## Safe Pytest Allowlist

Use only the focused import test added for this recovery:

```bash
PYTHONPYCACHEPREFIX=/tmp/lmcp_pycache .venv/bin/python -m pytest -q tests/test_router_imports_python39.py
```

Do not run broad `pytest` collection during this recovery unless the unsafe tests above are renamed, isolated, or explicitly excluded.
