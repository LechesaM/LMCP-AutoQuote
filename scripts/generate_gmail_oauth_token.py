#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from app.services.gmail_oauth_provider import GMAIL_DRAFT_SCOPES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Gmail OAuth token for LMCP AutoQuote draft-only transport."
    )
    parser.add_argument(
        "--credentials",
        default="secrets/gmail/credentials.json",
        help="Path to the Google Desktop OAuth client credentials JSON.",
    )
    parser.add_argument(
        "--token",
        default="secrets/gmail/token.json",
        help="Path where the authorised-user token JSON will be written.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Local callback port. Use 0 to select an available port automatically.",
    )
    return parser.parse_args()


def ensure_private_file(path: Path) -> None:
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError as exc:
        raise RuntimeError(f"Unable to apply secure permissions to {path}: {exc}") from exc


def validate_client_credentials(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"OAuth credentials file not found: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"OAuth credentials file is not valid JSON: {path}") from exc

    if "installed" not in payload:
        raise ValueError(
            "The OAuth credentials file is not a Desktop app credential. "
            "Expected a top-level 'installed' object."
        )


def main() -> int:
    args = parse_args()

    credentials_path = Path(args.credentials).expanduser().resolve()
    token_path = Path(args.token).expanduser().resolve()

    try:
        validate_client_credentials(credentials_path)

        token_path.parent.mkdir(parents=True, exist_ok=True)

        print("LMCP AutoQuote Gmail OAuth bootstrap")
        print(f"Credentials: {credentials_path}")
        print(f"Token destination: {token_path}")
        print(f"Requested scope: {GMAIL_DRAFT_SCOPES[0]}")
        print()
        print("Sign in only with the authorised LMCP supplier mailbox.")
        print("This flow requests Gmail compose access for draft creation.")
        print()

        flow = InstalledAppFlow.from_client_secrets_file(
            str(credentials_path),
            scopes=GMAIL_DRAFT_SCOPES,
        )

        credentials = flow.run_local_server(
            host="localhost",
            port=args.port,
            authorization_prompt_message=(
                "Open this URL in your browser to authorise LMCP AutoQuote:\n{url}"
            ),
            success_message=(
                "LMCP AutoQuote Gmail authorisation completed. "
                "You may close this browser window."
            ),
            open_browser=True,
            access_type="offline",
            prompt="consent",
        )

        token_path.write_text(credentials.to_json(), encoding="utf-8")
        ensure_private_file(token_path)

        print()
        print("OAuth token created successfully.")
        print(f"Saved to: {token_path}")
        print("Permissions set to owner read/write only.")
        print("No email was sent and no Gmail draft was created.")
        return 0

    except KeyboardInterrupt:
        print("\nAuthorisation cancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"OAuth bootstrap failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
