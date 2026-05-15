#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FULL_CYCLE = ROOT / "app/services/full_autonomous_cycle_service.py"
EMAIL_SERVICE = ROOT / "app/services/email_submission_service.py"


def backup(path: Path) -> None:
    if path.exists():
        dst = path.with_suffix(path.suffix + f".bak_auto_proof_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        dst.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Backup: {dst}")


def patch_full_cycle() -> bool:
    if not FULL_CYCLE.exists():
        print(f"MISSING: {FULL_CYCLE}")
        return False

    text = FULL_CYCLE.read_text(encoding="utf-8")

    if "auto_generate_submission_proof(history_record)" in text:
        print("OK: full_autonomous_cycle_service.py already patched")
        return False

    target = '''            _append_submission_history(history_record)
            item["history_record"] = history_record
'''

    replacement = '''            _append_submission_history(history_record)
            item["history_record"] = history_record

            try:
                from app.services.auto_proof_after_submission_service import auto_generate_submission_proof

                proof_result = auto_generate_submission_proof(history_record)
                item["proof_result"] = proof_result
                if isinstance(proof_result, dict):
                    history_record["proof_result"] = proof_result
                    if proof_result.get("proof_pdf_path"):
                        history_record["proof_pdf_path"] = proof_result.get("proof_pdf_path")
            except Exception as proof_exc:
                item["proof_result"] = {
                    "status": "failed",
                    "proof_generated": False,
                    "error": str(proof_exc),
                }
'''

    if target not in text:
        print("WARNING: Could not find exact full cycle insertion point.")
        print("Manual target: after _append_submission_history(history_record)")
        return False

    backup(FULL_CYCLE)
    FULL_CYCLE.write_text(text.replace(target, replacement), encoding="utf-8")
    print("CHANGED: app/services/full_autonomous_cycle_service.py")
    return True


def patch_email_service() -> bool:
    if not EMAIL_SERVICE.exists():
        print(f"MISSING: {EMAIL_SERVICE}")
        return False

    text = EMAIL_SERVICE.read_text(encoding="utf-8")

    if "auto_generate_submission_proof(history_payload)" in text:
        print("OK: email_submission_service.py already patched")
        return False

    target = '''            log_submission_event(
                cls._build_submission_history_payload(
                    payload=payload,
                    send_result=send_result,
                    attachment_paths=attachment_paths,
                    to_email=to_email,
                    cc_email=cc_email,
                    bcc_email=bcc_email,
                    subject=subject,
                )
            )
'''

    replacement = '''            history_payload = cls._build_submission_history_payload(
                payload=payload,
                send_result=send_result,
                attachment_paths=attachment_paths,
                to_email=to_email,
                cc_email=cc_email,
                bcc_email=bcc_email,
                subject=subject,
            )

            log_submission_event(history_payload)

            try:
                from app.services.auto_proof_after_submission_service import auto_generate_submission_proof

                proof_result = auto_generate_submission_proof(history_payload)
                if isinstance(proof_result, dict):
                    send_result["proof_result"] = proof_result
                    if proof_result.get("proof_pdf_path"):
                        send_result["proof_pdf_path"] = proof_result.get("proof_pdf_path")
            except Exception as proof_exc:
                send_result["proof_result"] = {
                    "status": "failed",
                    "proof_generated": False,
                    "error": str(proof_exc),
                }
'''

    if target not in text:
        print("WARNING: Could not find exact email service insertion point.")
        print("Manual target: inside _log_submission_history_if_available after log_submission_event(...)")
        return False

    backup(EMAIL_SERVICE)
    EMAIL_SERVICE.write_text(text.replace(target, replacement), encoding="utf-8")
    print("CHANGED: app/services/email_submission_service.py")
    return True


def main() -> int:
    print("LMCP AUTO-GENERATE PROOF AFTER SUBMISSION PATCH")
    print("=" * 55)

    patch_full_cycle()
    patch_email_service()

    print("\nDone.")
    print("Next:")
    print("python3 -m py_compile app/services/auto_proof_after_submission_service.py app/services/full_autonomous_cycle_service.py app/services/email_submission_service.py app/services/proof_of_submission_service.py app/main.py")
    print("docker compose restart api")
    print("sleep 8")
    print("curl -X POST http://localhost:8000/full-autonomous-cycle/run")
    print("curl http://localhost:8000/submission-proof/status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
