from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


GMAIL_DRAFT_SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


class GmailAuthUnavailable(Exception):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status
        self.message = message

    def to_dict(self) -> Dict[str, str]:
        return {"status": self.status, "message": self.message}


@dataclass
class GmailOAuthConfig:
    client_secret_file: str = ""
    token_file: str = ""
    user_id: str = "me"

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> "GmailOAuthConfig":
        env = env or os.environ
        return cls(
            client_secret_file=env.get("LMCP_GMAIL_CLIENT_SECRET_FILE")
            or env.get("LMCP_GMAIL_CREDENTIALS_FILE")
            or env.get("GMAIL_CLIENT_SECRET_FILE")
            or "",
            token_file=env.get("LMCP_GMAIL_TOKEN_FILE") or env.get("GMAIL_TOKEN_FILE") or "",
            user_id=env.get("LMCP_GMAIL_USER_ID") or "me",
        )


def redact_secret_path(path: str) -> str:
    if not path:
        return ""
    p = Path(path)
    return str(p.parent / ("<redacted-" + p.name[-8:] + ">"))


class GmailOAuthProvider:
    def __init__(self, config: Optional[GmailOAuthConfig] = None):
        self.config = config or GmailOAuthConfig.from_env()

    def inspect_configuration(self) -> Dict[str, Any]:
        deps = self._dependency_status()
        client_path = Path(self.config.client_secret_file) if self.config.client_secret_file else None
        token_path = Path(self.config.token_file) if self.config.token_file else None
        if not self.config.client_secret_file:
            status = "configuration_missing"
        elif not client_path or not client_path.exists():
            status = "credential_file_missing"
        elif not self.config.token_file:
            status = "token_file_missing"
        elif not token_path or not token_path.exists():
            status = "token_file_missing"
        elif not all(deps.values()):
            status = "dependency_unavailable"
        else:
            status = "configured"
        return {
            "status": status,
            "dependencies": deps,
            "client_secret_file": "configured" if self.config.client_secret_file else "missing",
            "token_file": "configured" if self.config.token_file else "missing",
            "user_id": self.config.user_id or "me",
            "scope": GMAIL_DRAFT_SCOPES[0],
            "redacted_client_secret_file": redact_secret_path(self.config.client_secret_file),
            "redacted_token_file": redact_secret_path(self.config.token_file),
        }

    def get_authenticated_client(self) -> Any:
        inspection = self.inspect_configuration()
        if inspection["status"] != "configured":
            raise GmailAuthUnavailable(inspection["status"], "Gmail OAuth client is not configured for draft transport.")

        try:
            from google.oauth2.credentials import Credentials  # type: ignore
            from googleapiclient.discovery import build  # type: ignore
        except Exception as exc:
            raise GmailAuthUnavailable("dependency_unavailable", "Gmail API dependencies are unavailable.") from exc

        credentials = Credentials.from_authorized_user_file(self.config.token_file, scopes=GMAIL_DRAFT_SCOPES)
        if not credentials.valid:
            raise GmailAuthUnavailable("token_refresh_required", "Gmail OAuth token is not currently valid.")
        return build("gmail", "v1", credentials=credentials)

    @staticmethod
    def _dependency_status() -> Dict[str, bool]:
        def available(module: str) -> bool:
            try:
                return importlib.util.find_spec(module) is not None
            except Exception:
                return False

        return {
            "googleapiclient": available("googleapiclient"),
            "google.oauth2": available("google.oauth2"),
            "google_auth_oauthlib": available("google_auth_oauthlib"),
        }
