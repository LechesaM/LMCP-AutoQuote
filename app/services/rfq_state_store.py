from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / "runtime"
RFQ_LIFECYCLE_DIR = RUNTIME_DIR / "rfq_lifecycle"
RFQ_STATE_FILE = RFQ_LIFECYCLE_DIR / "rfqs.json"
RFQ_AUDIT_FILE = RFQ_LIFECYCLE_DIR / "audit_events.json"
RFQ_ANALYTICS_FILE = RFQ_LIFECYCLE_DIR / "analytics.json"
RFQ_TELEMETRY_FILE = RFQ_LIFECYCLE_DIR / "telemetry.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RfqStateStore:
    def __init__(self, state_file: Path = RFQ_STATE_FILE) -> None:
        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def _default_payload(self) -> Dict[str, Any]:
        return {
            "version": "rfq_lifecycle_v1",
            "updated_at": utc_now_iso(),
            "items": {},
            "throughput": {
                "ingested": 0,
                "advanced": 0,
                "failed": 0,
                "recovered": 0,
                "retried": 0,
                "golden_cycles": 0,
            },
            "golden_validation": {
                "status": "not_run",
                "total_cycles_run": 0,
                "successful_cycles": 0,
                "recovered_rfqs": 0,
                "failed_cycles": 0,
                "average_cycle_time": 0.0,
                "retry_success_rate": 0.0,
                "last_run_at": "",
                "last_result": {},
            },
            "scale_simulation": {
                "active": False,
                "status": "not_run",
                "runs": 0,
                "last_run_at": "",
                "simulated_throughput": 0.0,
                "average_rfq_completion_time": 0.0,
                "queue_pressure": "idle",
                "worker_load": 0.0,
                "stage_bottlenecks": [],
                "throughput_trend": [],
                "lifecycle_analytics": {
                    "average_stage_time": {},
                    "max_queue_depth": 0,
                    "bottleneck_stage": "",
                    "retry_pressure": 0.0,
                    "proof_generation_rate": 0.0,
                },
                "last_result": {},
            },
        }

    def read(self) -> Dict[str, Any]:
        if not self.state_file.exists():
            payload = self._default_payload()
            self.write(payload)
            return payload
        try:
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("RFQ lifecycle state must be a JSON object")
        except Exception:
            corrupt = self.state_file.with_suffix(f".corrupt-{int(datetime.now().timestamp())}.json")
            try:
                self.state_file.replace(corrupt)
            except Exception:
                pass
            raw = self._default_payload()
            raw["alerts"] = [f"State file was corrupt and recreated; backup={corrupt}"]
            self.write(raw)

        raw.setdefault("version", "rfq_lifecycle_v1")
        raw.setdefault("updated_at", utc_now_iso())
        raw.setdefault("items", {})
        raw.setdefault("throughput", {})
        for key in ["ingested", "advanced", "failed", "recovered", "retried", "golden_cycles"]:
            raw["throughput"].setdefault(key, 0)
        raw.setdefault("golden_validation", {})
        for key, default in {
            "status": "not_run",
            "total_cycles_run": 0,
            "successful_cycles": 0,
            "recovered_rfqs": 0,
            "failed_cycles": 0,
            "average_cycle_time": 0.0,
            "retry_success_rate": 0.0,
            "last_run_at": "",
            "last_result": {},
        }.items():
            raw["golden_validation"].setdefault(key, default)
        raw.setdefault("scale_simulation", {})
        for key, default in {
            "active": False,
            "status": "not_run",
            "runs": 0,
            "last_run_at": "",
            "simulated_throughput": 0.0,
            "average_rfq_completion_time": 0.0,
            "queue_pressure": "idle",
            "worker_load": 0.0,
            "stage_bottlenecks": [],
            "throughput_trend": [],
            "last_result": {},
        }.items():
            raw["scale_simulation"].setdefault(key, default)
        raw["scale_simulation"].setdefault("lifecycle_analytics", {})
        for key, default in {
            "average_stage_time": {},
            "max_queue_depth": 0,
            "bottleneck_stage": "",
            "retry_pressure": 0.0,
            "proof_generation_rate": 0.0,
        }.items():
            raw["scale_simulation"]["lifecycle_analytics"].setdefault(key, default)
        return raw

    def write(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload["updated_at"] = utc_now_iso()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = self.state_file.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp_file, self.state_file)
        return payload

    def list_items(self) -> List[Dict[str, Any]]:
        items = self.read().get("items", {})
        if not isinstance(items, dict):
            return []
        return list(items.values())

    def get_item(self, rfq_id: str) -> Optional[Dict[str, Any]]:
        item = self.read().get("items", {}).get(rfq_id)
        return item if isinstance(item, dict) else None

    def upsert_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        payload = self.read()
        rfq_id = str(item["rfq_id"])
        payload["items"][rfq_id] = item
        return self.write(payload)["items"][rfq_id]

    def update_many(self, items: List[Dict[str, Any]], throughput_delta: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        payload = self.read()
        for item in items:
            payload["items"][str(item["rfq_id"])] = item
        if throughput_delta:
            for key, delta in throughput_delta.items():
                payload["throughput"][key] = int(payload["throughput"].get(key, 0)) + int(delta)
        return self.write(payload)

    def increment(self, key: str, amount: int = 1) -> Dict[str, Any]:
        payload = self.read()
        payload["throughput"][key] = int(payload["throughput"].get(key, 0)) + int(amount)
        return self.write(payload)

    def read_audit(self) -> Dict[str, Any]:
        if not RFQ_AUDIT_FILE.exists():
            payload = {"version": "rfq_lifecycle_audit_v1", "updated_at": utc_now_iso(), "events": []}
            self.write_audit(payload)
            return payload
        try:
            payload = json.loads(RFQ_AUDIT_FILE.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("RFQ audit store must be a JSON object")
        except Exception:
            payload = {"version": "rfq_lifecycle_audit_v1", "updated_at": utc_now_iso(), "events": []}
            self.write_audit(payload)
        payload.setdefault("version", "rfq_lifecycle_audit_v1")
        payload.setdefault("updated_at", utc_now_iso())
        payload.setdefault("events", [])
        return payload

    def write_audit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload["updated_at"] = utc_now_iso()
        RFQ_AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = RFQ_AUDIT_FILE.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp_file, RFQ_AUDIT_FILE)
        return payload

    def append_audit_events(self, events: List[Dict[str, Any]], max_events: int = 10000) -> Dict[str, Any]:
        if not events:
            return self.read_audit()
        payload = self.read_audit()
        current = payload.get("events") if isinstance(payload.get("events"), list) else []
        current.extend(events)
        payload["events"] = current[-max(1, int(max_events)) :]
        return self.write_audit(payload)

    def read_analytics(self) -> Dict[str, Any]:
        if not RFQ_ANALYTICS_FILE.exists():
            payload = {"version": "rfq_lifecycle_analytics_v1", "updated_at": utc_now_iso(), "analytics": {}}
            self.write_analytics(payload)
            return payload
        try:
            payload = json.loads(RFQ_ANALYTICS_FILE.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("RFQ analytics store must be a JSON object")
        except Exception:
            payload = {"version": "rfq_lifecycle_analytics_v1", "updated_at": utc_now_iso(), "analytics": {}}
            self.write_analytics(payload)
        payload.setdefault("version", "rfq_lifecycle_analytics_v1")
        payload.setdefault("updated_at", utc_now_iso())
        payload.setdefault("analytics", {})
        return payload

    def write_analytics(self, analytics: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "version": "rfq_lifecycle_analytics_v1",
            "updated_at": utc_now_iso(),
            "analytics": analytics,
        }
        RFQ_ANALYTICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = RFQ_ANALYTICS_FILE.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp_file, RFQ_ANALYTICS_FILE)
        return payload

    def read_telemetry(self) -> Dict[str, Any]:
        if not RFQ_TELEMETRY_FILE.exists():
            payload = {"version": "rfq_lifecycle_telemetry_v1", "updated_at": utc_now_iso(), "telemetry": {}, "history": []}
            RFQ_TELEMETRY_FILE.parent.mkdir(parents=True, exist_ok=True)
            RFQ_TELEMETRY_FILE.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            return payload
        try:
            payload = json.loads(RFQ_TELEMETRY_FILE.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("RFQ telemetry store must be a JSON object")
        except Exception:
            payload = {"version": "rfq_lifecycle_telemetry_v1", "updated_at": utc_now_iso(), "telemetry": {}, "history": []}
            RFQ_TELEMETRY_FILE.parent.mkdir(parents=True, exist_ok=True)
            RFQ_TELEMETRY_FILE.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        payload.setdefault("version", "rfq_lifecycle_telemetry_v1")
        payload.setdefault("updated_at", utc_now_iso())
        payload.setdefault("telemetry", {})
        payload.setdefault("history", [])
        return payload

    def write_telemetry(self, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        previous = self.read_telemetry() if RFQ_TELEMETRY_FILE.exists() else {"history": []}
        history = previous.get("history") if isinstance(previous.get("history"), list) else []
        history.append(
            {
                "at": utc_now_iso(),
                "system_resilience_score": telemetry.get("system_resilience_score"),
                "broker_connected": (telemetry.get("broker_health") or {}).get("connected"),
                "online_workers": len((telemetry.get("worker_heartbeat") or {}).get("online_workers") or []),
                "queue_backlog_total": (telemetry.get("queue_backlog") or {}).get("total_backlog"),
                "stalled_lifecycle_tasks": len(telemetry.get("stalled_lifecycle_tasks") or []),
            }
        )
        payload = {
            "version": "rfq_lifecycle_telemetry_v1",
            "updated_at": utc_now_iso(),
            "telemetry": telemetry,
            "history": history[-250:],
        }
        RFQ_TELEMETRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = RFQ_TELEMETRY_FILE.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp_file, RFQ_TELEMETRY_FILE)
        return payload
