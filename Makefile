PYTHON ?= python3
PILOT_WORKSPACE_ROOT ?= /Users/cash/Documents/lmcp_pilot_runs
PILOT_IDS ?= PILOT-001 PILOT-002 PILOT-003
FRONTEND_DIR ?= /Users/cash/Documents/frontend/command-centre
PILOT_WEEK_WORKSPACE_ROOT ?= /Users/cash/Documents/runtime/manual_production
PILOT_WEEK_ID ?= PILOT-001
PILOT_WEEK_TENDER_ID ?= REAL-PILOT-001
PILOT_WEEK_TENDER_ROOT ?= /Users/cash/Documents/runtime/manual_production/source_bundle_repairs/REAL-PILOT-001
PILOT_WEEK_PRICING_FILE ?= /Users/cash/Documents/runtime/manual_production/submission_packages/REAL-PILOT-001/REAL-PILOT-001__manual_pricing_restored_from_governed_quote_pack.json
PILOT_WEEK_OPERATOR_NAME ?= Supervisor
PILOT_WEEK_PORTAL_NAME ?= Metro Procurement Unit
PILOT_WEEK_SUBMISSION_REFERENCE ?= REAL-PILOT-001__submission__20260528T141144Z
PILOT_WEEK_PROOF_FILE ?= /Users/cash/Documents/runtime/manual_production/submission_executions/REAL-PILOT-001/REAL_PILOT_001_submission_proof/REAL_PILOT_001_submission_receipt_20260528T141144Z.txt
DAILY_PILOT_WORKSPACE_ROOT ?= /Users/cash/Documents/runtime/manual_production
DAILY_PILOT_OPERATOR_NAME ?= Supervisor
DAILY_PILOT_QUEUE_FILE ?= /Users/cash/Documents/runtime/live_rfqs.json
HARVEST_SOURCE_FILE ?= /Users/cash/Documents/app/data/harvest_sources.json
HARVEST_FALLBACK_FIXTURE ?= /Users/cash/Documents/tests/fixtures/real_pilot_rfqs/real_pilot_valid_office_consumables_001.json
QUEUE_REFRESH_SOURCE_FILE ?= /Users/cash/Documents/app/data/queue_refresh_sources.json

.PHONY: pilot-batch pilot-batch-one pilot-week pilot-week-dry-run fresh-intake queue-refresh bootstrap-live-queue-candidates normalize-live-queue-candidates prune-completed-live-queue-candidates repair-refresh-bundle-source-artifacts live-queue-status daily-pilot-loop morning-ritual repair-pricing-bundles repair-pdf-artifacts controlled-operation-check autoquote-libraries-check

pilot-batch:
	$(PYTHON) scripts/run_workspace_pilot_batch.py --workspace-root $(PILOT_WORKSPACE_ROOT)

pilot-batch-one:
	$(PYTHON) scripts/run_workspace_pilot.py --workspace-root $(PILOT_WORKSPACE_ROOT) --pilot-id $(PILOT_ID)

pilot-week:
	$(PYTHON) scripts/run_supervised_pilot_week.py \
		--workspace-root $(PILOT_WEEK_WORKSPACE_ROOT) \
		--pilot-id $(PILOT_WEEK_ID) \
		--tender-id $(PILOT_WEEK_TENDER_ID) \
		--tender-root $(PILOT_WEEK_TENDER_ROOT) \
		--pricing-file $(PILOT_WEEK_PRICING_FILE) \
		--confirm-approval \
		--operator-name $(PILOT_WEEK_OPERATOR_NAME) \
		--record-proof \
		--portal-name "$(PILOT_WEEK_PORTAL_NAME)" \
		--submission-reference "$(PILOT_WEEK_SUBMISSION_REFERENCE)" \
		--proof-file $(PILOT_WEEK_PROOF_FILE)

pilot-week-dry-run:
	$(PYTHON) scripts/run_supervised_pilot_week.py \
		--workspace-root $(PILOT_WEEK_WORKSPACE_ROOT) \
		--pilot-id $(PILOT_WEEK_ID) \
		--tender-id $(PILOT_WEEK_TENDER_ID) \
		--tender-root $(PILOT_WEEK_TENDER_ROOT) \
		--pricing-file $(PILOT_WEEK_PRICING_FILE) \
		--confirm-approval \
		--operator-name $(PILOT_WEEK_OPERATOR_NAME)

fresh-intake:
	$(PYTHON) scripts/run_fixture_backed_fresh_intake.py \
		--harvest-source-file $(HARVEST_SOURCE_FILE) \
		--fallback-fixture $(HARVEST_FALLBACK_FIXTURE) \
		--queue-file $(DAILY_PILOT_QUEUE_FILE)

queue-refresh:
	$(PYTHON) scripts/run_fixture_backed_fresh_intake.py \
		--harvest-source-file $(QUEUE_REFRESH_SOURCE_FILE) \
		--require-live-harvest \
		--queue-file $(DAILY_PILOT_QUEUE_FILE)

bootstrap-live-queue-candidates:
	$(PYTHON) scripts/bootstrap_remaining_live_queue_candidates.py \
		--queue-file $(DAILY_PILOT_QUEUE_FILE)

normalize-live-queue-candidates:
	$(PYTHON) scripts/normalize_live_queue_candidates.py \
		--queue-file $(DAILY_PILOT_QUEUE_FILE)

prune-completed-live-queue-candidates:
	$(PYTHON) scripts/prune_completed_live_queue_candidates.py \
		--queue-file $(DAILY_PILOT_QUEUE_FILE)

repair-refresh-bundle-source-artifacts:
	$(PYTHON) scripts/repair_refresh_bundle_source_artifacts.py

live-queue-status:
	$(PYTHON) scripts/live_queue_status.py \
		--queue-file $(DAILY_PILOT_QUEUE_FILE)

daily-pilot-loop:
	$(PYTHON) scripts/run_daily_pilot_loop.py \
		--workspace-root $(DAILY_PILOT_WORKSPACE_ROOT) \
		--operator-name $(DAILY_PILOT_OPERATOR_NAME) \
		--queue-file $(DAILY_PILOT_QUEUE_FILE) \
		--report-file /Users/cash/Documents/runtime/manual_production/daily_pilot_loop_report.json

morning-ritual:
	$(PYTHON) scripts/check_controlled_operation_readiness.py && \
	$(PYTHON) scripts/live_queue_status.py \
		--queue-file $(DAILY_PILOT_QUEUE_FILE) \
		--fail-if-empty && \
	$(PYTHON) scripts/run_daily_pilot_loop.py \
		--workspace-root $(DAILY_PILOT_WORKSPACE_ROOT) \
		--operator-name $(DAILY_PILOT_OPERATOR_NAME) \
		--fresh-only \
		--queue-file $(DAILY_PILOT_QUEUE_FILE) \
		--report-file /Users/cash/Documents/runtime/manual_production/daily_pilot_loop_report.json

repair-pricing-bundles:
	$(PYTHON) scripts/repair_zero_pricing_bundles.py

repair-pdf-artifacts:
	$(PYTHON) scripts/repair_invalid_pdf_artifacts.py

controlled-operation-check:
	$(PYTHON) scripts/check_controlled_operation_readiness.py

autoquote-libraries-check:
	cd $(FRONTEND_DIR) && npm run check:autoquote-libraries
