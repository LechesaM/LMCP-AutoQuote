
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import traceback

from app.core.runtime_paths import get_runtime_paths

LEGACY_SERVICE = True
SERVICE_VERSION = "V48_FULL_AUTONOMOUS_ORCHESTRATOR"
DEFAULT_OUTPUT_DIR = get_runtime_paths().runtime_root / "full_autonomous_v48"
DEFAULT_STATE_PATH = get_runtime_paths().runtime_root / "system_control" / "v48_autonomous_state.json"
DEFAULT_HISTORY_PATH = get_runtime_paths().runtime_root / "submission_history" / "v48_autonomous_runs.json"
DEFAULT_CDP_URL = "http://host.docker.internal:9222"

DEFAULT_POLICY = {
    "enabled": False,
    "mode": "safe",
    "allow_email_send": False,
    "allow_portal_upload": False,
    "allow_portal_final_submit": False,
    "require_confirmation_phrase": False,
    "confirmation_phrase": "I CONFIRM FINAL SUBMISSION",
    "minimum_profit_required": 30000.0,
    "margin_percent": 25.0,
    "apply_profit_floor": True,
    "min_confidence": 0.35,
    "zip_allowed_for_submission": False,
    "captcha_bypass_allowed": False,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_path(value: str | Path) -> Path:
    raw = str(value)

    if raw.startswith("/app - "):
        raw = raw.split(":/app/runtime", 1)[-1]
        if raw.startswith("/runtime/"):
            raw = raw.replace("/runtime/", "runtime/", 1)

    if raw.startswith("/app/runtime/"):
        return Path(raw)

    if raw.startswith("runtime/"):
        return Path("/app") / raw

    p = Path(raw)
    if not p.is_absolute():
        p = Path("/app") / p
    return p


def _safe_name(value: Any, fallback: str = "RUN") -> str:
    import re
    text = str(value or fallback).strip()
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-")
    return text or fallback


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_json(path: Path, fallback: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback


def _state_path() -> Path:
    return _resolve_path(DEFAULT_STATE_PATH)


def _history_path() -> Path:
    return _resolve_path(DEFAULT_HISTORY_PATH)


def _load_policy() -> Dict[str, Any]:
    state = _read_json(_state_path(), {}) or {}
    policy = {**DEFAULT_POLICY, **(state.get("policy") or {})}
    return policy


def _save_policy(policy: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "service_version": SERVICE_VERSION,
        "updated_at": _now_iso(),
        "policy": {**DEFAULT_POLICY, **policy},
    }
    _write_json(_state_path(), payload)
    return payload


def _append_history(record: Dict[str, Any]) -> None:
    path = _history_path()
    data = _read_json(path, []) or []
    if not isinstance(data, list):
        data = []
    data.append(record)
    _write_json(path, data)


def set_v48_autonomous_policy(
    enabled: Optional[bool] = None,
    mode: Optional[str] = None,
    allow_email_send: Optional[bool] = None,
    allow_portal_upload: Optional[bool] = None,
    allow_portal_final_submit: Optional[bool] = None,
    minimum_profit_required: Optional[float] = None,
    margin_percent: Optional[float] = None,
) -> Dict[str, Any]:
    policy = _load_policy()

    if enabled is not None:
        policy["enabled"] = bool(enabled)
    if mode is not None:
        policy["mode"] = mode
    if allow_email_send is not None:
        policy["allow_email_send"] = bool(allow_email_send)
    if allow_portal_upload is not None:
        policy["allow_portal_upload"] = bool(allow_portal_upload)
    if allow_portal_final_submit is not None:
        policy["allow_portal_final_submit"] = bool(allow_portal_final_submit)
    if minimum_profit_required is not None:
        policy["minimum_profit_required"] = float(minimum_profit_required)
    if margin_percent is not None:
        policy["margin_percent"] = float(margin_percent)

    # Safety rule: final submit is only possible in controlled mode with explicit opt-in.
    if policy.get("mode") not in {"controlled", "production"}:
        policy["allow_portal_final_submit"] = False
        policy["require_confirmation_phrase"] = bool(policy.get("require_confirmation_phrase", False))

    return _save_policy(policy)


def get_v48_status() -> Dict[str, Any]:
    policy = _load_policy()
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "service": "V48 Full Autonomous Orchestrator",
        "description": "Runs the LMCP chain from PDF/RFQ into pricing, quote pack, submission pack, email/portal preparation, portal upload, guarded final submit, verification, and audit register.",
        "policy": policy,
        "state_path": str(_state_path()),
        "history_path": str(_history_path()),
        "default_output_dir": str(DEFAULT_OUTPUT_DIR),
        "endpoints": {
            "status": "/v48-autonomous/status",
            "policy": "/v48-autonomous/policy",
            "run_from_pdf": "/v48-autonomous/run-from-pdf",
            "run_from_v45_workspace": "/v48-autonomous/run-from-v45-workspace",
        },
        "ready": True,
    }


def _make_workspace(buyer_rfq_number: str, output_dir: Optional[str]) -> Path:
    root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    if not root.is_absolute():
        root = Path.cwd() / root
    workspace = root / f"{_safe_name(buyer_rfq_number)}__AUTO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _record_stage(stages: List[Dict[str, Any]], name: str, status: str, result: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> None:
    stages.append({
        "stage": name,
        "status": status,
        "at": _now_iso(),
        "summary": _summarise_result(result),
        "error": error,
    })


def _summarise_result(result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    keys = [
        "status", "message", "buyer_rfq_number", "quote_number", "workspace",
        "service_version", "input_pdf", "blocked_reason", "cdp_resolved",
        "profile_mode", "auth_mode", "matched_row", "final_block_reason",
        "authenticated_indicators_found", "auth_diagnostic_screenshot",
        "target_terms_used", "all_visible_row_previews_scanned",
        "pagination_rounds_attempted", "best_candidate_row",
        "row_clicked", "row_expanded", "expanded_dom_detected",
        "tender_detail_detected", "upload_controls_detected",
        "active_tab_name", "start_response_clicked", "categorieslist_visible",
        "response_session_started", "response_workspace_loaded",
        "persistent_expanded_row", "workspace_recovered", "workspace_page_reused",
        "url_transition_detected", "before_start_response_screenshot",
        "after_start_response_activation_screenshot",
        "response_workspace_url", "response_workspace_title", "active_iframe_url",
        "dom_replacement_detected", "workspace_transition_success",
        "expanded_row_controls", "attempted_click_targets", "click_dispatch_results",
        "start_response_debug_artifact", "expanded_row_html_artifact",
        "scanned_rows_count", "skipped_rows_count",
        "successful_workspace_transition_count", "row_classification",
        "summary_counts_by_reason", "top_possible_candidates",
        "start_response_candidates", "selected_row_index",
        "workspace_transition_url", "scan_termination_reason",
        "visible_controls", "hidden_controls", "delayed_controls",
        "iframe_controls", "shadowdom_controls",
        "hidden_start_response_candidates", "delayed_render_detected",
        "iframe_detected", "shadowdom_detected",
        "mutation_added_controls_count", "hidden_control_reveal_attempts",
        "successful_hidden_control_reveals",
        "initial_portal_view", "detected_tabs", "detected_filters",
        "activated_esubmission_view", "filter_changes",
        "post_filter_scanned_rows_count",
        "post_filter_esubmission_candidates_count",
        "no_esubmission_root_cause", "view_debug_artifacts",
        "searched_views", "searched_filter_sets", "eligible_candidates_found",
        "candidate_confidence_scores", "best_candidate_summary",
        "candidate_response_controls", "discovery_termination_reason",
        "eligible_candidates_report_json", "top_candidate_screenshots",
        "successful_discovery_page_snapshots",
    ]
    out = {k: result.get(k) for k in keys if k in result}
    if "totals" in result:
        out["totals"] = result.get("totals")
    if "assessment" in result:
        out["assessment"] = result.get("assessment")
    if "artifacts" in result:
        out["artifacts"] = result.get("artifacts")
    return out


def _resolve_cdp_for_v48(cdp_url: Optional[str]) -> Dict[str, Any]:
    try:
        from app.services.etenders_dom_modal_autoclick_v50_9_4_service import _resolve_cdp_endpoint

        return _resolve_cdp_endpoint(cdp_url or DEFAULT_CDP_URL)
    except Exception as exc:
        return {
            "ok": False,
            "input_cdp_url": cdp_url or DEFAULT_CDP_URL,
            "resolved_websocket_url": "",
            "error": str(exc),
        }


def _find_latest_autofill_plan(portal_manifest_result: Dict[str, Any]) -> Optional[str]:
    # V47.1 creates a new workspace; easiest is to return artifact path if present.
    artifacts = portal_manifest_result.get("artifacts") or {}
    return artifacts.get("autofill_plan_json")


def run_v48_from_pdf(
    input_pdf: str,
    buyer_rfq_number: str,
    buyer_name: Optional[str] = None,
    portal_url: Optional[str] = "https://www.etenders.gov.za",
    submission_method: str = "portal",
    cdp_url: Optional[str] = None,
    output_dir: Optional[str] = None,
    override_policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    started_at = _now_iso()
    policy = {**_load_policy(), **(override_policy or {})}
    workspace = _make_workspace(buyer_rfq_number, output_dir)
    stages: List[Dict[str, Any]] = []

    result: Dict[str, Any] = {
        "status": "started",
        "service_version": SERVICE_VERSION,
        "buyer_rfq_number": buyer_rfq_number,
        "buyer_name": buyer_name,
        "submission_method": submission_method,
        "input_pdf": input_pdf,
        "workspace": str(workspace),
        "started_at": started_at,
        "policy": policy,
        "stages": stages,
    }

    try:
        if not policy.get("enabled"):
            result.update({
                "status": "blocked_disabled",
                "message": "V48 autonomous mode is disabled. Enable policy before running autonomous execution.",
                "completed_at": _now_iso(),
            })
            _write_json(workspace / "v48_autonomous_run.json", result)
            _append_history(result)
            return result

        # Stage 1: V45 from PDF creates V43 + V44 + V45 artifacts.
        from app.services.submission_pack_v45_service import prepare_submission_from_pdf

        v45 = prepare_submission_from_pdf(
            input_pdf=input_pdf,
            buyer_rfq_number=buyer_rfq_number,
            margin_percent=float(policy.get("margin_percent", 25.0)),
            minimum_profit_required=float(policy.get("minimum_profit_required", 30000.0)),
            apply_profit_floor=bool(policy.get("apply_profit_floor", True)),
            min_confidence=float(policy.get("min_confidence", 0.35)),
            create_zip=True,
        )
        _record_stage(stages, "v45_prepare_submission_pack_from_pdf", v45.get("status", "unknown"), v45)

        if v45.get("status") not in {"ok", "prepared"}:
            result.update({"status": "failed_v45", "completed_at": _now_iso(), "last_result": v45})
            _write_json(workspace / "v48_autonomous_run.json", result)
            _append_history(result)
            return result

        if submission_method == "email":
            return _continue_v48_email(result, stages, v45, buyer_rfq_number, policy, workspace)

        return _continue_v48_portal(
            result=result,
            stages=stages,
            v45=v45,
            buyer_rfq_number=buyer_rfq_number,
            buyer_name=buyer_name,
            portal_url=portal_url,
            cdp_url=cdp_url,
            policy=policy,
            workspace=workspace,
        )

    except Exception as exc:
        result.update({
            "status": "error",
            "message": "V48 autonomous run failed.",
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "completed_at": _now_iso(),
        })
        _write_json(workspace / "v48_autonomous_run.json", result)
        _append_history(result)
        return result


def run_v48_from_v45_workspace(
    v45_workspace: str,
    buyer_rfq_number: str,
    buyer_name: Optional[str] = None,
    portal_url: Optional[str] = "https://www.etenders.gov.za",
    submission_method: str = "portal",
    cdp_url: Optional[str] = None,
    output_dir: Optional[str] = None,
    override_policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    started_at = _now_iso()
    policy = {**_load_policy(), **(override_policy or {})}
    workspace = _make_workspace(buyer_rfq_number, output_dir)
    stages: List[Dict[str, Any]] = []

    result: Dict[str, Any] = {
        "status": "started",
        "service_version": SERVICE_VERSION,
        "buyer_rfq_number": buyer_rfq_number,
        "buyer_name": buyer_name,
        "submission_method": submission_method,
        "v45_workspace": v45_workspace,
        "workspace": str(workspace),
        "started_at": started_at,
        "policy": policy,
        "stages": stages,
    }

    try:
        if not policy.get("enabled"):
            result.update({
                "status": "blocked_disabled",
                "message": "V48 autonomous mode is disabled. Enable policy before running autonomous execution.",
                "completed_at": _now_iso(),
            })
            _write_json(workspace / "v48_autonomous_run.json", result)
            _append_history(result)
            return result

        v45 = {"status": "ok", "workspace": str(_resolve_path(v45_workspace))}
        _record_stage(stages, "v45_existing_workspace", "ok", v45)

        if submission_method == "email":
            return _continue_v48_email(result, stages, v45, buyer_rfq_number, policy, workspace)

        return _continue_v48_portal(
            result=result,
            stages=stages,
            v45=v45,
            buyer_rfq_number=buyer_rfq_number,
            buyer_name=buyer_name,
            portal_url=portal_url,
            cdp_url=cdp_url,
            policy=policy,
            workspace=workspace,
        )

    except Exception as exc:
        result.update({
            "status": "error",
            "message": "V48 autonomous run from V45 workspace failed.",
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "completed_at": _now_iso(),
        })
        _write_json(workspace / "v48_autonomous_run.json", result)
        _append_history(result)
        return result


def _continue_v48_email(result: Dict[str, Any], stages: List[Dict[str, Any]], v45: Dict[str, Any], buyer_rfq_number: str, policy: Dict[str, Any], workspace: Path) -> Dict[str, Any]:
    from app.services.auto_submission_v46_service import submit_from_v45_workspace

    send = bool(policy.get("allow_email_send"))
    v46 = submit_from_v45_workspace(
        workspace_path=v45.get("workspace"),
        buyer_rfq_number=buyer_rfq_number,
        dry_run=not send,
        allow_send=send,
    )
    _record_stage(stages, "v46_email_submission", v46.get("status", "unknown"), v46)

    result.update({
        "status": "email_sent" if v46.get("status") == "sent" else "email_dry_run",
        "completed_at": _now_iso(),
        "last_result": v46,
    })
    _write_json(workspace / "v48_autonomous_run.json", result)
    _append_history(result)
    return result


def _continue_v48_portal(
    result: Dict[str, Any],
    stages: List[Dict[str, Any]],
    v45: Dict[str, Any],
    buyer_rfq_number: str,
    buyer_name: Optional[str],
    portal_url: Optional[str],
    cdp_url: Optional[str],
    policy: Dict[str, Any],
    workspace: Path,
) -> Dict[str, Any]:
    cdp_resolution = _resolve_cdp_for_v48(cdp_url)
    effective_cdp_url = cdp_resolution.get("resolved_websocket_url") or cdp_url or DEFAULT_CDP_URL
    result["cdp_resolved"] = cdp_resolution
    result.setdefault("profile_mode", "live_cdp" if cdp_resolution.get("ok") else "persistent_profile_or_storage_state")

    # Stage 2: V47 portal pack.
    from app.services.portal_submission_v47_service import prepare_portal_submission_from_v45_workspace

    v47 = prepare_portal_submission_from_v45_workspace(
        workspace_path=v45.get("workspace"),
        buyer_rfq_number=buyer_rfq_number,
        buyer_name=buyer_name,
        portal_url=portal_url,
        require_operator_confirmation=True,
    )
    _record_stage(stages, "v47_portal_pack", v47.get("status", "unknown"), v47)

    if v47.get("status") not in {"prepared", "ok"}:
        result.update({"status": "failed_v47_portal_pack", "completed_at": _now_iso(), "last_result": v47})
        _write_json(workspace / "v48_autonomous_run.json", result)
        _append_history(result)
        return result

    # Stage 3: V47.1 autofill plan.
    from app.services.portal_form_autofill_v47_1_service import generate_portal_form_autofill_plan

    v471 = generate_portal_form_autofill_plan(
        portal_manifest_json=(v47.get("artifacts") or {}).get("portal_manifest_json"),
    )
    _record_stage(stages, "v47_1_autofill_plan", v471.get("status", "unknown"), v471)

    # V50.9.4: live eTenders DOM row discovery / modal autoclick / row expansion.
    # This runs before V47.4/V47.5 so the browser is positioned on the real opportunity table.
    try:
        from app.services.etenders_dom_modal_autoclick_v50_9_4_service import capture_dom_modal_autoclick

        v5094 = capture_dom_modal_autoclick({
            "tender_id": buyer_rfq_number,
            "search_text": (
                buyer_rfq_number
                or v471.get("buyer_rfq_number")
                or "DIGITAL BOOK JDA"
            ),
            "title": (
                v471.get("title")
                or v471.get("buyer_rfq_number")
                or buyer_rfq_number
                or "DIGITAL BOOK JDA"
            ),
            "tender_url": "https://www.etenders.gov.za/Home/opportunities?id=1",
            "cdp_url": effective_cdp_url,
            "supportDocumentID": (
                v471.get("supportDocumentID")
                or ((v471.get("navigation_resolution") or {}).get("supportDocumentID"))
            ),
            "wait_seconds": 20,
        })

        _record_stage(stages, "v50_9_4_etenders_row_discovery", v5094.get("status", "unknown"), v5094)
        result["matched_row"] = v5094.get("matched_row")
        result["target_terms_used"] = v5094.get("target_terms_used") or []
        result["all_visible_row_previews_scanned"] = v5094.get("all_visible_row_previews_scanned") or []
        result["pagination_rounds_attempted"] = v5094.get("pagination_rounds_attempted") or 0
        result["best_candidate_row"] = v5094.get("best_candidate_row")
        result["row_clicked"] = bool(v5094.get("row_clicked"))
        result["row_expanded"] = bool(v5094.get("row_expanded"))
        result["expanded_dom_detected"] = bool(v5094.get("expanded_dom_detected"))
        result["tender_detail_detected"] = bool(v5094.get("tender_detail_detected"))
        result["upload_controls_detected"] = bool(v5094.get("upload_controls_detected"))

    except Exception as exc:
        v5094 = {
            "status": "error",
            "message": "V50.9.4 eTenders row discovery failed.",
            "error": str(exc),
        }
        _record_stage(stages, "v50_9_4_etenders_row_discovery", "error", v5094)

    autofill_plan_json = (v471.get("artifacts") or {}).get("autofill_plan_json")
    if not autofill_plan_json:
        result.update({"status": "failed_v47_1_no_plan", "completed_at": _now_iso(), "last_result": v471})
        _write_json(workspace / "v48_autonomous_run.json", result)
        _append_history(result)
        return result

    # Stage 4: V47.4 smart upload; only upload if policy allows it.
    from app.services.smart_upload_v47_4_service import attach_and_smart_upload

    import asyncio

    upload_allowed = bool(policy.get("allow_portal_upload"))

    v474 = asyncio.run(
        attach_and_smart_upload(
            autofill_plan_json=autofill_plan_json,
            cdp_url=effective_cdp_url,
                stop_before_submit=True,
        )
    )
    _record_stage(stages, "v47_4_smart_upload", v474.get("status", "unknown"), v474)

    if not upload_allowed:
        result.update({
            "status": "portal_prepared_upload_not_executed",
            "message": "Portal upload was planned but not executed because allow_portal_upload=false.",
            "autofill_plan_json": autofill_plan_json,
            "completed_at": _now_iso(),
            "last_result": v474,
        })
        _write_json(workspace / "v48_autonomous_run.json", result)
        _append_history(result)
        return result

    # Stage 5: V47.5 final submit; only if policy allows.
    from app.services.final_submission_v47_5_service import guarded_final_submission

    final_allowed = bool(policy.get("allow_portal_final_submit"))

    v475 = asyncio.run(
        guarded_final_submission(
            autofill_plan_json=autofill_plan_json,
            cdp_url=effective_cdp_url,
            confirmation_phrase=policy.get("confirmation_phrase"),
            allow_final_submit=final_allowed,
            payload={
                "matched_row": result.get("matched_row"),
                "row_clicked": result.get("row_clicked"),
                "row_expanded": result.get("row_expanded"),
                "expanded_dom_detected": result.get("expanded_dom_detected"),
                "tender_detail_detected": result.get("tender_detail_detected"),
                "upload_controls_detected": result.get("upload_controls_detected"),
            },
        )
    )
    _record_stage(stages, "v47_5_guarded_final_submit", v475.get("status", "unknown"), v475)
    result["profile_mode"] = v475.get("profile_mode") or result.get("profile_mode")
    result["auth_mode"] = v475.get("auth_mode")
    result["final_block_reason"] = v475.get("final_block_reason") or v475.get("reason")
    start_response_result = v475.get("start_response_result") if isinstance(v475.get("start_response_result"), dict) else {}
    for key in [
        "active_tab_name",
        "start_response_clicked",
        "categorieslist_visible",
        "response_session_started",
        "response_workspace_loaded",
        "persistent_expanded_row",
        "workspace_recovered",
        "url_transition_detected",
        "before_start_response_screenshot",
        "after_start_response_activation_screenshot",
        "response_workspace_url",
        "response_workspace_title",
        "active_iframe_url",
        "dom_replacement_detected",
        "workspace_transition_success",
        "expanded_row_controls",
        "attempted_click_targets",
        "click_dispatch_results",
        "start_response_debug_artifact",
        "expanded_row_html_artifact",
        "scanned_rows_count",
        "skipped_rows_count",
        "successful_workspace_transition_count",
        "row_classification",
        "summary_counts_by_reason",
        "top_possible_candidates",
        "start_response_candidates",
        "visible_controls",
        "hidden_controls",
        "delayed_controls",
        "iframe_controls",
        "shadowdom_controls",
        "hidden_start_response_candidates",
        "delayed_render_detected",
        "iframe_detected",
        "shadowdom_detected",
        "mutation_added_controls_count",
        "hidden_control_reveal_attempts",
        "successful_hidden_control_reveals",
        "selected_row_index",
        "workspace_transition_url",
        "scan_termination_reason",
        "initial_portal_view",
        "detected_tabs",
        "detected_filters",
        "activated_esubmission_view",
        "filter_changes",
        "post_filter_scanned_rows_count",
        "post_filter_esubmission_candidates_count",
        "no_esubmission_root_cause",
        "view_debug_artifacts",
        "searched_views",
        "searched_filter_sets",
        "eligible_candidates_found",
        "candidate_confidence_scores",
        "best_candidate_summary",
        "candidate_response_controls",
        "discovery_termination_reason",
        "eligible_candidates_report_json",
        "top_candidate_screenshots",
        "successful_discovery_page_snapshots",
    ]:
        if key in start_response_result:
            result[key] = start_response_result.get(key)
    result["workspace_page_reused"] = bool(v475.get("workspace_page_reused"))

    if not final_allowed:
        result.update({
            "status": "portal_uploaded_final_submit_not_executed",
            "message": "Portal upload executed, but final submit was not executed because allow_portal_final_submit=false.",
            "autofill_plan_json": autofill_plan_json,
            "completed_at": _now_iso(),
            "last_result": v475,
        })
        _write_json(workspace / "v48_autonomous_run.json", result)
        _append_history(result)
        return result

    # Stage 6: V47.6 and V47.7 verification.
    from app.services.submission_verification_v47_6_service import verify_live_submission
    v476 = verify_live_submission(
        buyer_rfq_number=buyer_rfq_number,
        quote_number=v47.get("quote_number"),
        final_submission_run_json=(v475.get("artifacts") or {}).get("final_submission_run_json"),
        cdp_url=effective_cdp_url,
        navigate_to_profile_responses=True,
    )
    _record_stage(stages, "v47_6_submission_verification", v476.get("status", "unknown"), v476)

    from app.services.deep_verification_v47_7_service import run_deep_verification_audit
    v477 = run_deep_verification_audit(
        buyer_rfq_number=buyer_rfq_number,
        quote_number=v47.get("quote_number"),
        final_submission_run_json=(v475.get("artifacts") or {}).get("final_submission_run_json"),
        verification_v47_6_json=(v476.get("artifacts") or {}).get("verification_json"),
        cdp_url=effective_cdp_url,
        navigate_to_profile_responses=True,
        expand_matching_row=True,
    )
    _record_stage(stages, "v47_7_deep_verification_audit", v477.get("status", "unknown"), v477)

    result.update({
        "status": "verified_submitted" if v477.get("status") == "verified_submitted" else "submitted_needs_review",
        "autofill_plan_json": autofill_plan_json,
        "completed_at": _now_iso(),
        "verification": _summarise_result(v477),
        "last_result": v477,
    })
    _write_json(workspace / "v48_autonomous_run.json", result)
    _append_history(result)
    return result
