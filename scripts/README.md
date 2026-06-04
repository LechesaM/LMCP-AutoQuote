# Scripts

Useful local operator entrypoints:

- `make controlled-proof`
  - Seeds controlled runtime state
  - Starts the API
  - Verifies `/health`, `/system/control/effective-status`, and `/health/workflows`
  - Runs validate -> quote pack -> pricing schedule -> submission package
- `make controlled-proof-report`
  - Prints the saved controlled proof summary from the latest logs
- `python3 scripts/show_controlled_proof_report.py`
  - Prints a compact summary from the saved controlled proof JSON log
- `bash scripts/start_local_manual_production.sh`
  - Starts the backend and frontend for the manual production pilot flow
- `python3 scripts/check_local_system.py`
  - Checks whether the local manual-production backend and frontend are ready
