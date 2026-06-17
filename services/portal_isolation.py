import json
import logging
import os
import threading
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.utcnow()


def to_iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() + "Z" if dt else None


@dataclass
class PortalHealth:
    portal_slug: str
    portal_name: str
    failure_count: int = 0
    success_count: int = 0
    last_error: Optional[str] = None
    last_checked_at: Optional[str] = None
    last_success_at: Optional[str] = None
    last_failure_at: Optional[str] = None
    isolated_until: Optional[str] = None
    isolation_reason: Optional[str] = None
    is_isolated: bool = False


class PortalIsolationManager:
    """
    Protects the harvester from unstable portals.

    Rules:
    - repeated failures isolate a portal temporarily
    - isolated portals are skipped
    - healthy portals continue harvesting
    - isolation expires automatically
    """

    def __init__(
        self,
        state_file: Optional[str] = None,
        failure_threshold: int = 3,
        isolation_minutes: int = 60,
        enabled: bool = True,
    ) -> None:
        if state_file is None:
            state_file = str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "portal_isolation_state.json")
        self.state_file = state_file
        self.failure_threshold = failure_threshold
        self.isolation_minutes = isolation_minutes
        self.enabled = enabled
        self._lock = threading.Lock()
        self._state: Dict[str, PortalHealth] = {}

        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.state_file):
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                raw = json.load(f)

            for portal_slug, data in raw.items():
                self._state[portal_slug] = PortalHealth(**data)
        except Exception as exc:
            logger.warning("Failed to load portal isolation state: %s", exc)

    def _save(self) -> None:
        try:
            payload = {slug: asdict(health) for slug, health in self._state.items()}
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as exc:
            logger.warning("Failed to save portal isolation state: %s", exc)

    def _get_or_create(self, portal_slug: str, portal_name: Optional[str] = None) -> PortalHealth:
        if portal_slug not in self._state:
            self._state[portal_slug] = PortalHealth(
                portal_slug=portal_slug,
                portal_name=portal_name or portal_slug,
            )
        else:
            if portal_name:
                self._state[portal_slug].portal_name = portal_name
        return self._state[portal_slug]

    def _parse_iso(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", ""))
        except Exception:
            return None

    def _refresh_isolation_state(self, health: PortalHealth) -> None:
        if not health.isolated_until:
            health.is_isolated = False
            return

        until = self._parse_iso(health.isolated_until)
        if not until:
            health.is_isolated = False
            health.isolated_until = None
            return

        if utcnow() >= until:
            health.is_isolated = False
            health.isolated_until = None
            health.isolation_reason = None
            health.failure_count = 0

    def should_skip(self, portal_slug: str, portal_name: Optional[str] = None) -> bool:
        if not self.enabled:
            return False

        with self._lock:
            health = self._get_or_create(portal_slug, portal_name)
            self._refresh_isolation_state(health)
            self._save()
            return health.is_isolated

    def record_success(self, portal_slug: str, portal_name: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            health = self._get_or_create(portal_slug, portal_name)
            self._refresh_isolation_state(health)

            health.success_count += 1
            health.failure_count = 0
            health.last_error = None
            health.last_checked_at = to_iso(utcnow())
            health.last_success_at = to_iso(utcnow())

            if health.is_isolated:
                health.is_isolated = False
                health.isolated_until = None
                health.isolation_reason = None

            self._save()
            return asdict(health)

    def record_failure(
        self,
        portal_slug: str,
        portal_name: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            health = self._get_or_create(portal_slug, portal_name)
            self._refresh_isolation_state(health)

            health.failure_count += 1
            health.last_error = (error or "unknown_error")[:1000]
            health.last_checked_at = to_iso(utcnow())
            health.last_failure_at = to_iso(utcnow())

            if self.enabled and health.failure_count >= self.failure_threshold:
                isolated_until = utcnow() + timedelta(minutes=self.isolation_minutes)
                health.is_isolated = True
                health.isolated_until = to_iso(isolated_until)
                health.isolation_reason = f"failure_threshold_reached:{health.failure_count}"

                logger.warning(
                    "Portal isolated: %s until %s بسبب repeated failures",
                    portal_slug,
                    health.isolated_until,
                )

            self._save()
            return asdict(health)

    def unisolate(self, portal_slug: str) -> Dict[str, Any]:
        with self._lock:
            health = self._get_or_create(portal_slug)
            health.is_isolated = False
            health.isolated_until = None
            health.isolation_reason = None
            health.failure_count = 0
            health.last_checked_at = to_iso(utcnow())
            self._save()
            return asdict(health)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            isolated = 0
            healthy = 0
            portals: Dict[str, Any] = {}

            for slug, health in self._state.items():
                self._refresh_isolation_state(health)
                portals[slug] = asdict(health)
                if health.is_isolated:
                    isolated += 1
                else:
                    healthy += 1

            self._save()

            return {
                "enabled": self.enabled,
                "failure_threshold": self.failure_threshold,
                "isolation_minutes": self.isolation_minutes,
                "total_portals_tracked": len(self._state),
                "healthy_portals": healthy,
                "isolated_portals": isolated,
                "portals": portals,
            }


portal_isolation_manager = PortalIsolationManager(
    state_file=os.getenv(
        "PORTAL_ISOLATION_STATE_FILE",
        str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "portal_isolation_state.json"),
    ),
    failure_threshold=int(os.getenv("PORTAL_ISOLATION_FAILURE_THRESHOLD", "3")),
    isolation_minutes=int(os.getenv("PORTAL_ISOLATION_MINUTES", "60")),
    enabled=os.getenv("PORTAL_ISOLATION_ENABLED", "true").lower() == "true",
)
