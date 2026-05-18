from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping, Tuple


def _clean_env(environ: Mapping[str, str], name: str, default: str) -> str:
    value = str(environ.get(name, "")).strip()
    return value or default


def _resolve_path(value: str, *, base: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def resolve_project_root(environ: Mapping[str, str] | None = None) -> Path:
    source = environ if environ is not None else os.environ
    default_root = Path(__file__).resolve().parents[2]
    raw = _clean_env(source, "LMCP_PROJECT_ROOT", str(default_root))
    return _resolve_path(raw, base=default_root)


@dataclass(frozen=True)
class RuntimePaths:
    project_root: Path
    runtime_root: Path
    logs_dir: Path
    downloads_dir: Path
    proofs_dir: Path
    submissions_dir: Path
    final_submission_dir: Path
    proof_center_dir: Path
    manual_production_dir: Path
    temp_dir: Path
    exports_dir: Path
    operator_auth_dir: Path
    operator_auth_db_path: Path
    handwriting_runtime_dir: Path
    tender_form_runtime_dir: Path
    clickable_navigation_runtime_dir: Path
    audit_trail_dir: Path
    submission_history_dir: Path
    health_dir: Path
    locks_dir: Path

    @classmethod
    def from_environ(cls, environ: Mapping[str, str] | None = None) -> "RuntimePaths":
        source = environ if environ is not None else os.environ
        project_root = resolve_project_root(source)
        runtime_root = _resolve_path(_clean_env(source, "LMCP_RUNTIME_DIR", str(project_root / "runtime")), base=project_root)
        return cls(
            project_root=project_root,
            runtime_root=runtime_root,
            logs_dir=_resolve_path(_clean_env(source, "LMCP_LOG_DIR", str(runtime_root / "logs")), base=project_root),
            downloads_dir=_resolve_path(_clean_env(source, "LMCP_MONTHLY_QUOTES_DIR", str(project_root / "monthly_quotes")), base=project_root),
            proofs_dir=_resolve_path(_clean_env(source, "LMCP_SUBMISSION_PROOFS_DIR", str(runtime_root / "submission_proofs")), base=project_root),
            submissions_dir=_resolve_path(_clean_env(source, "LMCP_PORTAL_SUBMISSION_DIR", str(runtime_root / "portal_submission")), base=project_root),
            final_submission_dir=_resolve_path(_clean_env(source, "LMCP_FINAL_SUBMISSION_DIR", str(runtime_root / "final_submission_v47_5")), base=project_root),
            proof_center_dir=_resolve_path(_clean_env(source, "LMCP_PROOF_CENTER_DIR", str(runtime_root / "proof_center")), base=project_root),
            manual_production_dir=_resolve_path(_clean_env(source, "LMCP_MANUAL_PRODUCTION_DIR", str(runtime_root / "manual_production")), base=project_root),
            temp_dir=_resolve_path(_clean_env(source, "LMCP_TEMP_DIR", str(runtime_root / "tmp")), base=project_root),
            exports_dir=_resolve_path(_clean_env(source, "LMCP_EXPORTS_DIR", str(runtime_root / "exports")), base=project_root),
            operator_auth_dir=_resolve_path(_clean_env(source, "LMCP_OPERATOR_AUTH_DIR", str(runtime_root / "operator_auth")), base=project_root),
            operator_auth_db_path=_resolve_path(
                _clean_env(source, "LMCP_OPERATOR_AUTH_DB_PATH", str(runtime_root / "operator_auth" / "operator_auth.sqlite3")),
                base=project_root,
            ),
            handwriting_runtime_dir=_resolve_path(
                _clean_env(source, "LMCP_HANDWRITING_RUNTIME_DIR", str(runtime_root / "handwriting_simulation")),
                base=project_root,
            ),
            tender_form_runtime_dir=_resolve_path(
                _clean_env(source, "LMCP_TENDER_FORM_RUNTIME_DIR", str(runtime_root / "tender_form_intelligence")),
                base=project_root,
            ),
            clickable_navigation_runtime_dir=_resolve_path(
                _clean_env(source, "LMCP_CLICKABLE_NAVIGATION_RUNTIME_DIR", str(runtime_root / "clickable_navigation_v40")),
                base=project_root,
            ),
            audit_trail_dir=_resolve_path(_clean_env(source, "LMCP_AUDIT_TRAIL_DIR", str(runtime_root / "audit_trail")), base=project_root),
            submission_history_dir=_resolve_path(
                _clean_env(source, "LMCP_SUBMISSION_HISTORY_DIR", str(runtime_root / "submission_history")),
                base=project_root,
            ),
            health_dir=_resolve_path(_clean_env(source, "LMCP_HEALTH_DIR", str(runtime_root / "health")), base=project_root),
            locks_dir=_resolve_path(_clean_env(source, "LMCP_LOCKS_DIR", str(runtime_root / "locks")), base=project_root),
        )

    def required_directories(self) -> Tuple[Path, ...]:
        return (
            self.runtime_root,
            self.logs_dir,
            self.downloads_dir,
            self.proofs_dir,
            self.submissions_dir,
            self.final_submission_dir,
            self.proof_center_dir,
            self.manual_production_dir,
            self.temp_dir,
            self.exports_dir,
            self.operator_auth_dir,
            self.handwriting_runtime_dir,
            self.tender_form_runtime_dir,
            self.clickable_navigation_runtime_dir,
            self.audit_trail_dir,
            self.submission_history_dir,
            self.health_dir,
            self.locks_dir,
            self.operator_auth_db_path.parent,
        )

    def ensure_directories(self) -> None:
        for directory in self.required_directories():
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_runtime_paths() -> RuntimePaths:
    paths = RuntimePaths.from_environ()
    paths.ensure_directories()
    return paths
