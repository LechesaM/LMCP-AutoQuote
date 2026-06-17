from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class ComplianceDocumentService:
    """
    Central service for resolving compliance/supporting documents
    such as CSD report, CIPC docs, tax compliance docs, B-BBEE, IDs, etc.

    For now, this file focuses strongly on latest CSD document resolution,
    but the structure allows easy extension.
    """

    DEFAULT_CSD_DIR = str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "csd_reports")

    @staticmethod
    def _safe_str(value: Any, default: str = "") -> str:
        if value is None:
            return default
        return str(value).strip() or default

    @classmethod
    def _env(cls, name: str, default: Optional[str] = None) -> str:
        value = os.getenv(name, default)
        return cls._safe_str(value, default or "")

    @classmethod
    def _path_exists(cls, value: str) -> bool:
        try:
            return Path(value).expanduser().exists()
        except Exception:
            return False

    @classmethod
    def _is_allowed_doc(cls, path: Path) -> bool:
        allowed = {
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".csv",
            ".zip",
            ".xml",
        }
        return path.is_file() and path.suffix.lower() in allowed

    @classmethod
    def _collect_files_recursive(cls, root_dir: Path) -> List[Path]:
        if not root_dir.exists() or not root_dir.is_dir():
            return []

        files: List[Path] = []
        for item in root_dir.rglob("*"):
            if cls._is_allowed_doc(item):
                files.append(item)
        return files

    @classmethod
    def _file_sort_key(cls, path: Path) -> float:
        try:
            return path.stat().st_mtime
        except Exception:
            return 0.0

    @classmethod
    def _normalize_doc_entry(
        cls,
        *,
        label: str,
        path: str,
        category: str,
        source: str,
        required: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        metadata = metadata or {}
        return {
            "label": cls._safe_str(label),
            "path": cls._safe_str(path),
            "filename": Path(path).name if path else "",
            "category": cls._safe_str(category),
            "source": cls._safe_str(source),
            "required": bool(required),
            "exists": cls._path_exists(path),
            "metadata": metadata,
        }

    # ------------------------------------------------------------------
    # CSD resolution
    # ------------------------------------------------------------------

    @classmethod
    def get_csd_base_dir(cls) -> Path:
        configured = cls._env("CSD_REPORT_STORAGE_DIR", cls.DEFAULT_CSD_DIR)
        return Path(configured).expanduser()

    @classmethod
    def get_latest_csd_report(cls) -> Optional[Dict[str, Any]]:
        """
        Returns metadata for the newest CSD report found under the configured
        CSD report storage directory.
        """
        base_dir = cls.get_csd_base_dir()
        files = cls._collect_files_recursive(base_dir)

        if not files:
            return None

        csd_like_files: List[Path] = []
        for file_path in files:
            name = file_path.name.lower()
            folder = str(file_path.parent).lower()
            if "csd" in name or "csd" in folder:
                csd_like_files.append(file_path)

        if not csd_like_files:
            csd_like_files = files

        csd_like_files.sort(key=cls._file_sort_key, reverse=True)
        latest = csd_like_files[0]

        try:
            stat = latest.stat()
            modified_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
            size = stat.st_size
        except Exception:
            modified_at = ""
            size = 0

        return cls._normalize_doc_entry(
            label="Latest CSD Report",
            path=str(latest),
            category="csd_report",
            source="runtime_csd_storage",
            required=False,
            metadata={
                "modified_at": modified_at,
                "size_bytes": size,
                "parent_folder": str(latest.parent),
            },
        )

    @classmethod
    def resolve_csd_report(
        cls,
        explicit_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Resolution order:
        1. explicit path if valid
        2. env override LMCP_CSD_REPORT_PATH if valid
        3. latest report in runtime/csd_reports
        """
        if explicit_path and cls._path_exists(explicit_path):
            return cls._normalize_doc_entry(
                label="CSD Report",
                path=explicit_path,
                category="csd_report",
                source="explicit_path",
                required=False,
            )

        env_path = cls._env("LMCP_CSD_REPORT_PATH", "")
        if env_path and cls._path_exists(env_path):
            return cls._normalize_doc_entry(
                label="CSD Report",
                path=env_path,
                category="csd_report",
                source="env_override",
                required=False,
            )

        return cls.get_latest_csd_report()

    # ------------------------------------------------------------------
    # Other compliance docs
    # ------------------------------------------------------------------

    @classmethod
    def resolve_optional_doc_from_env(
        cls,
        env_name: str,
        *,
        label: str,
        category: str,
    ) -> Optional[Dict[str, Any]]:
        path = cls._env(env_name, "")
        if not path or not cls._path_exists(path):
            return None

        return cls._normalize_doc_entry(
            label=label,
            path=path,
            category=category,
            source=f"env:{env_name}",
            required=False,
        )

    @classmethod
    def get_default_compliance_documents(
        cls,
        include_csd: bool = True,
    ) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []

        if include_csd:
            csd_doc = cls.resolve_csd_report()
            if csd_doc:
                docs.append(csd_doc)

        optional_env_docs = [
            ("LMCP_CIPC_DOC_PATH", "CIPC Registration Document", "cipc"),
            ("LMCP_TAX_PIN_DOC_PATH", "SARS Tax Compliance / TCS PIN", "tax"),
            ("LMCP_BBBEE_DOC_PATH", "B-BBEE Certificate", "bbb ee"),
            ("LMCP_DIRECTOR_ID_DOC_PATH", "Director ID Copy", "director_id"),
        ]

        for env_name, label, category in optional_env_docs:
            doc = cls.resolve_optional_doc_from_env(
                env_name,
                label=label,
                category=category,
            )
            if doc:
                docs.append(doc)

        return docs

    @classmethod
    def merge_compliance_documents(
        cls,
        existing_docs: Optional[List[Dict[str, Any]]] = None,
        include_defaults: bool = True,
    ) -> List[Dict[str, Any]]:
        existing_docs = existing_docs or []
        merged: List[Dict[str, Any]] = []

        if include_defaults:
            merged.extend(cls.get_default_compliance_documents())

        merged.extend(existing_docs)

        # deduplicate by normalized path
        deduped: List[Dict[str, Any]] = []
        seen = set()

        for doc in merged:
            path = cls._safe_str(doc.get("path")).strip()
            key = path.lower()
            if not path or key in seen:
                continue
            seen.add(key)
            deduped.append(doc)

        return deduped

    @classmethod
    def build_pack_attachment_paths(
        cls,
        existing_paths: Optional[List[str]] = None,
        include_default_compliance_docs: bool = True,
    ) -> List[str]:
        existing_paths = existing_paths or []
        merged_paths: List[str] = []

        for item in existing_paths:
            if item and cls._path_exists(item):
                merged_paths.append(item)

        if include_default_compliance_docs:
            for doc in cls.get_default_compliance_documents():
                path = cls._safe_str(doc.get("path"))
                if path and cls._path_exists(path):
                    merged_paths.append(path)

        # deduplicate while preserving order
        result: List[str] = []
        seen = set()
        for path in merged_paths:
            key = path.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(path)

        return result
