from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def now_ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def screenshot(page, proof_dir: Path, name: str) -> str:
    file_path = proof_dir / f"{name}.png"
    page.screenshot(path=str(file_path), full_page=True)
    return str(file_path)


def html_snapshot(page, proof_dir: Path, name: str) -> str:
    file_path = proof_dir / f"{name}.html"
    save_text(file_path, page.content())
    return str(file_path)


def normalize_docs(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    for category in ["mandatory", "essential", "non_essential", "other"]:
        for item in payload.get("documents", {}).get(category, []):
            p = Path(item["path"]).expanduser().resolve()
            docs.append(
                {
                    "category": category,
                    "label": item.get("label", p.name),
                    "path": str(p),
                    "exists": p.exists(),
                    "sha256": sha256_of_file(p) if p.exists() else None,
                    "size": p.stat().st_size if p.exists() else None,
                }
            )
    return docs


def click_first(page, selectors: List[str], timeout: int = 5000) -> bool:
    for sel in selectors:
        try:
            locator = page.locator(sel).first
            locator.wait_for(state="visible", timeout=timeout)
            locator.click()
            return True
        except Exception:
            continue
    return False


def fill_first(page, selectors: List[str], value: str, timeout: int = 5000) -> bool:
    for sel in selectors:
        try:
            locator = page.locator(sel).first
            locator.wait_for(state="visible", timeout=timeout)
            locator.fill(value)
            return True
        except Exception:
            continue
    return False


def upload_files_for_category(page, category_name: str, files: List[Dict[str, Any]], proof_dir: Path, logs: List[str]) -> None:
    if not files:
        logs.append(f"[SKIP] No files for category: {category_name}")
        return

    logs.append(f"[INFO] Uploading category: {category_name} | count={len(files)}")

    tab_candidates = [
        f"text={category_name.replace('_', ' ').title()}",
        f"text={category_name.replace('_', ' ').capitalize()}",
        f"role=tab[name*='{category_name}']",
    ]
    click_first(page, tab_candidates, timeout=3000)

    file_input_candidates = [
        "input[type='file']",
        "input[type=file]",
    ]

    for f in files:
        if not f["exists"]:
            logs.append(f"[MISSING] {f['path']}")
            continue

        uploaded = False
        for sel in file_input_candidates:
            try:
                locator = page.locator(sel).first
                locator.set_input_files(f["path"])
                time.sleep(2)
                logs.append(f"[OK] Uploaded: {f['label']} -> {f['path']}")
                uploaded = True
                screenshot(page, proof_dir, f"uploaded_{category_name}_{Path(f['path']).stem}")
                break
            except Exception as exc:
                logs.append(f"[WARN] Upload attempt failed for {f['path']} using {sel}: {exc}")

        if not uploaded:
            logs.append(f"[FAIL] Could not upload: {f['path']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True, help="Path to submission payload JSON")
    parser.add_argument("--profile-dir", required=True, help="Persistent Playwright profile directory")
    parser.add_argument("--proof-root", required=True, help="Where proof artifacts should be saved")
    parser.add_argument("--dry-run", action="store_true", help="Do everything except final submit click")
    args = parser.parse_args()

    payload_path = Path(args.payload).expanduser().resolve()
    profile_dir = Path(args.profile_dir).expanduser().resolve()
    proof_root = Path(args.proof_root).expanduser().resolve()

    if not payload_path.exists():
        print(f"Payload not found: {payload_path}")
        return 1

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    tender_reference = payload.get("tender_reference", "").strip()
    supplier_hint = payload.get("supplier_hint", "").strip()

    if not tender_reference:
        print("Payload must include tender_reference")
        return 1

    run_dir = ensure_dir(proof_root / f"{tender_reference}_{now_ts()}")
    logs: List[str] = []
    network_log: List[Dict[str, Any]] = []

    docs = normalize_docs(payload)
    save_json(run_dir / "manifest.json", {"payload": payload, "documents": docs})

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            accept_downloads=True,
            viewport={"width": 1440, "height": 1000},
        )

        page = browser.new_page()

        def on_response(resp):
            try:
                network_log.append(
                    {
                        "url": resp.url,
                        "status": resp.status,
                        "ok": resp.ok,
                        "content_type": resp.headers.get("content-type"),
                    }
                )
            except Exception:
                pass

        page.on("response", on_response)

        try:
            logs.append("[STEP] Open login page")
            page.goto("https://www.etenders.gov.za/Login/Login", wait_until="domcontentloaded", timeout=90000)
            screenshot(page, run_dir, "01_login_page")
            html_snapshot(page, run_dir, "01_login_page")

            logs.append("[STEP] Wait for persistent session or manual login")
            page.wait_for_timeout(5000)

            logs.append("[STEP] Open opportunities page")
            page.goto("https://www.etenders.gov.za/Home/opportunities", wait_until="domcontentloaded", timeout=90000)
            screenshot(page, run_dir, "02_opportunities")
            html_snapshot(page, run_dir, "02_opportunities")

            logs.append(f"[STEP] Search tender reference: {tender_reference}")
            search_ok = fill_first(
                page,
                [
                    "input[type='search']",
                    "input[name*='search']",
                    "input[placeholder*='Search']",
                    "input[placeholder*='search']",
                ],
                tender_reference,
                timeout=7000,
            )

            if search_ok:
                page.keyboard.press("Enter")
                page.wait_for_timeout(4000)
            else:
                logs.append("[WARN] Search input not found; continuing manually")

            screenshot(page, run_dir, "03_search_results")
            html_snapshot(page, run_dir, "03_search_results")

            logs.append("[STEP] Open matching tender / submission flow")
            opened = click_first(
                page,
                [
                    f"text={tender_reference}",
                    "text=Start eSubmission Process",
                    "text=Submit",
                    "text=eSubmission",
                    "a:has-text('Start eSubmission Process')",
                    "button:has-text('Start eSubmission Process')",
                ],
                timeout=7000,
            )

            if not opened:
                logs.append("[WARN] Could not auto-open tender. Manual intervention may be required.")
                screenshot(page, run_dir, "04_manual_intervention_needed")
                input("Open the correct tender and press ENTER to continue... ")

            page.wait_for_timeout(5000)
            screenshot(page, run_dir, "05_submission_start")
            html_snapshot(page, run_dir, "05_submission_start")

            if supplier_hint:
                logs.append(f"[STEP] Select supplier using hint: {supplier_hint}")
                fill_first(
                    page,
                    [
                        "input[placeholder*='supplier']",
                        "input[placeholder*='Supplier']",
                        "input[name*='supplier']",
                    ],
                    supplier_hint,
                    timeout=5000,
                )
                page.wait_for_timeout(2000)
                click_first(
                    page,
                    [
                        f"text={supplier_hint}",
                        "button:has-text('Select')",
                        "text=Select Supplier",
                    ],
                    timeout=4000,
                )

            screenshot(page, run_dir, "06_supplier_selected")

            docs_by_category: Dict[str, List[Dict[str, Any]]] = {
                "mandatory": [d for d in docs if d["category"] == "mandatory"],
                "essential": [d for d in docs if d["category"] == "essential"],
                "non_essential": [d for d in docs if d["category"] == "non_essential"],
                "other": [d for d in docs if d["category"] == "other"],
            }

            for category_name, file_list in docs_by_category.items():
                upload_files_for_category(page, category_name, file_list, run_dir, logs)

            screenshot(page, run_dir, "07_after_uploads")
            html_snapshot(page, run_dir, "07_after_uploads")

            logs.append("[STEP] Pause for CAPTCHA / manual checks if any")
            input("If the portal needs CAPTCHA or confirmation, complete it now, then press ENTER... ")

            screenshot(page, run_dir, "08_pre_submit")
            html_snapshot(page, run_dir, "08_pre_submit")

            if args.dry_run:
                logs.append("[DRY-RUN] Final submit intentionally skipped")
            else:
                logs.append("[STEP] Click final submit")
                submitted = click_first(
                    page,
                    [
                        "button:has-text('Submit')",
                        "input[value='Submit']",
                        "text=Submit",
                        "button:has-text('Confirm')",
                        "text=Confirm",
                    ],
                    timeout=7000,
                )

                if not submitted:
                    logs.append("[WARN] Final submit button not clicked automatically")
                    input("Click the final submit button manually, then press ENTER... ")

                page.wait_for_timeout(8000)
                screenshot(page, run_dir, "09_post_submit")
                html_snapshot(page, run_dir, "09_post_submit")

            save_json(run_dir / "network_log.json", network_log)
            save_text(run_dir / "run_log.txt", "\n".join(logs))

            print(f"Done. Proof saved to: {run_dir}")
            browser.close()
            return 0

        except PlaywrightTimeoutError as exc:
            logs.append(f"[TIMEOUT] {exc}")
            save_text(run_dir / "run_log.txt", "\n".join(logs))
            save_json(run_dir / "network_log.json", network_log)
            try:
                screenshot(page, run_dir, "error_timeout")
                html_snapshot(page, run_dir, "error_timeout")
            except Exception:
                pass
            print(f"Timeout. Proof saved to: {run_dir}")
            browser.close()
            return 2

        except Exception as exc:
            logs.append(f"[ERROR] {repr(exc)}")
            save_text(run_dir / "run_log.txt", "\n".join(logs))
            save_json(run_dir / "network_log.json", network_log)
            try:
                screenshot(page, run_dir, "error_general")
                html_snapshot(page, run_dir, "error_general")
            except Exception:
                pass
            print(f"Error. Proof saved to: {run_dir}")
            browser.close()
            return 3


if __name__ == "__main__":
    sys.exit(main())
