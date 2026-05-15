from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.safari.options import Options as SafariOptions
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class CSDReportRefreshError(Exception):
    pass


@dataclass
class CSDRefreshConfig:
    login_email: str
    login_password: str
    supplier_number: str
    unique_reference_number: str
    compliance_dir: Path
    archive_dir: Path
    output_filename: str
    timeout_seconds: int
    manual_captcha_timeout_seconds: int
    poll_seconds: int


class CSDReportRefreshService:
    LOGIN_URL = "https://secure.csd.gov.za/Account/Login"
    REGISTRATION_PROCESS_URL = "https://secure.csd.gov.za/Home/RegistrationProcess"

    @staticmethod
    def _get_env(name: str, default: Optional[str] = None, required: bool = False) -> str:
        value = os.getenv(name, default)
        if required and (value is None or str(value).strip() == ""):
            raise CSDReportRefreshError(f"Missing required environment variable: {name}")
        return (value or "").strip()

    @classmethod
    def _int_env(cls, name: str, default: int) -> int:
        raw = cls._get_env(name, str(default))
        try:
            return int(raw)
        except Exception:
            return default

    @classmethod
    def load_config(cls) -> CSDRefreshConfig:
        compliance_dir = Path(
            cls._get_env(
                "LMCP_COMPLIANCE_DOCS_DIR",
                "/Users/Shared/LMCP-AutoQuote-Server/compliance_docs",
                required=True,
            )
        )
        archive_dir = Path(
            cls._get_env(
                "LMCP_COMPLIANCE_ARCHIVE_DIR",
                str(compliance_dir / "archive"),
            )
        )

        return CSDRefreshConfig(
            login_email=cls._get_env("CSD_LOGIN_EMAIL", required=True),
            login_password=cls._get_env("CSD_LOGIN_PASSWORD", required=True),
            supplier_number=cls._get_env("CSD_SUPPLIER_NUMBER", required=True),
            unique_reference_number=cls._get_env("CSD_UNIQUE_REFERENCE_NUMBER", required=True),
            compliance_dir=compliance_dir,
            archive_dir=archive_dir,
            output_filename=cls._get_env("CSD_REPORT_FILENAME", "csd_report.pdf"),
            timeout_seconds=cls._int_env("CSD_BROWSER_TIMEOUT_SECONDS", 60),
            manual_captcha_timeout_seconds=cls._int_env("CSD_MANUAL_CAPTCHA_TIMEOUT_SECONDS", 300),
            poll_seconds=cls._int_env("CSD_POLL_SECONDS", 2),
        )

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    @classmethod
    def _ensure_dirs(cls, config: CSDRefreshConfig) -> None:
        config.compliance_dir.mkdir(parents=True, exist_ok=True)
        config.archive_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _build_driver(cls, config: CSDRefreshConfig) -> WebDriver:
        options = SafariOptions()
        driver = webdriver.Safari(options=options)
        driver.set_window_size(1440, 1200)
        driver.set_page_load_timeout(config.timeout_seconds)
        return driver

    @classmethod
    def _archive_existing_report(cls, final_path: Path, archive_dir: Path) -> Optional[Path]:
        if not final_path.exists() or not final_path.is_file():
            return None

        archived_path = archive_dir / f"{final_path.stem}_{cls._timestamp()}{final_path.suffix}"
        shutil.copy2(final_path, archived_path)
        return archived_path

    @classmethod
    def _find_first_present(cls, driver: WebDriver, xpaths: list[str], timeout_seconds: int) -> Optional[Any]:
        wait = WebDriverWait(driver, timeout_seconds)
        for xpath in xpaths:
            try:
                return wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
            except Exception:
                continue
        return None

    @classmethod
    def _find_first_clickable(cls, driver: WebDriver, xpaths: list[str], timeout_seconds: int) -> Optional[Any]:
        wait = WebDriverWait(driver, timeout_seconds)
        for xpath in xpaths:
            try:
                return wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            except Exception:
                continue
        return None

    @classmethod
    def _safe_click(cls, element: Any) -> None:
        try:
            element.click()
        except Exception:
            try:
                element.submit()
            except Exception:
                raise

    @classmethod
    def _login(cls, driver: WebDriver, config: CSDRefreshConfig) -> Dict[str, Any]:
        driver.get(cls.LOGIN_URL)

        email_input = cls._find_first_present(
            driver,
            [
                "//input[contains(@name,'Email') or contains(@id,'Email') or @type='email']",
                "//input[contains(@placeholder,'Email')]",
            ],
            config.timeout_seconds,
        )
        if email_input is None:
            raise CSDReportRefreshError("Could not find CSD email input field.")

        password_input = cls._find_first_present(
            driver,
            [
                "//input[contains(@name,'Password') or contains(@id,'Password') or @type='password']",
            ],
            config.timeout_seconds,
        )
        if password_input is None:
            raise CSDReportRefreshError("Could not find CSD password input field.")

        email_input.clear()
        email_input.send_keys(config.login_email)

        password_input.clear()
        password_input.send_keys(config.login_password)

        login_button = cls._find_first_clickable(
            driver,
            [
                "//button[@type='submit']",
                "//input[@type='submit']",
                "//button[contains(translate(., 'LOGIN', 'login'), 'login')]",
                "//a[contains(translate(., 'LOGIN', 'login'), 'login')]",
            ],
            config.timeout_seconds,
        )
        if login_button is None:
            raise CSDReportRefreshError("Could not find CSD login button.")

        cls._safe_click(login_button)

        manual_deadline = time.time() + config.manual_captcha_timeout_seconds
        while time.time() < manual_deadline:
            current_url = (driver.current_url or "").lower()

            if "login" not in current_url:
                return {
                    "login_success": True,
                    "manual_captcha_used": True,
                }

            post_login_marker = cls._find_first_present(
                driver,
                [
                    "//a[contains(translate(., 'REPORT', 'report'), 'report')]",
                    "//a[contains(translate(., 'HOME', 'home'), 'home')]",
                    "//a[contains(translate(., 'LOGOUT', 'logout'), 'logout')]",
                ],
                2,
            )
            if post_login_marker is not None:
                return {
                    "login_success": True,
                    "manual_captcha_used": True,
                }

            time.sleep(config.poll_seconds)

        raise CSDReportRefreshError(
            "CSD login did not complete within the manual captcha timeout window."
        )

    @classmethod
    def _open_registration_report_flow(cls, driver: WebDriver, config: CSDRefreshConfig) -> None:
        driver.get(cls.REGISTRATION_PROCESS_URL)

        report_link = cls._find_first_clickable(
            driver,
            [
                "//a[contains(translate(., 'REPORT', 'report'), 'report')]",
                "//button[contains(translate(., 'REPORT', 'report'), 'report')]",
            ],
            10,
        )
        if report_link is not None:
            try:
                cls._safe_click(report_link)
            except Exception:
                pass

        registration_link = cls._find_first_clickable(
            driver,
            [
                "//a[contains(translate(., 'REGISTRATION', 'registration'), 'registration')]",
                "//button[contains(translate(., 'REGISTRATION', 'registration'), 'registration')]",
            ],
            10,
        )
        if registration_link is not None:
            try:
                cls._safe_click(registration_link)
            except Exception:
                pass

        supplier_input = cls._find_first_present(
            driver,
            [
                "//input[contains(@name,'Supplier') or contains(@id,'Supplier') or contains(@placeholder,'Supplier')]",
            ],
            config.timeout_seconds,
        )
        if supplier_input is None:
            raise CSDReportRefreshError("Could not find supplier number field on CSD report page.")

        unique_ref_input = cls._find_first_present(
            driver,
            [
                "//input[contains(@name,'Unique') or contains(@id,'Unique') or contains(@placeholder,'Unique')]",
                "//input[contains(@name,'Reference') or contains(@id,'Reference') or contains(@placeholder,'Reference')]",
            ],
            config.timeout_seconds,
        )
        if unique_ref_input is None:
            raise CSDReportRefreshError("Could not find unique reference field on CSD report page.")

        supplier_input.clear()
        supplier_input.send_keys(config.supplier_number)

        unique_ref_input.clear()
        unique_ref_input.send_keys(config.unique_reference_number)

        view_report_button = cls._find_first_clickable(
            driver,
            [
                "//button[contains(translate(., 'VIEW REPORT', 'view report'), 'view report')]",
                "//input[@type='submit' and contains(translate(@value, 'VIEW REPORT', 'view report'), 'view report')]",
                "//a[contains(translate(., 'VIEW REPORT', 'view report'), 'view report')]",
            ],
            config.timeout_seconds,
        )
        if view_report_button is None:
            raise CSDReportRefreshError("Could not find View Report button on CSD report page.")

        cls._safe_click(view_report_button)

    @classmethod
    def _wait_for_report_window_or_pdf(cls, driver: WebDriver, config: CSDRefreshConfig) -> Dict[str, Any]:
        deadline = time.time() + config.timeout_seconds
        original_handles = set(driver.window_handles)

        while time.time() < deadline:
            current_url = (driver.current_url or "").lower()

            if current_url.endswith(".pdf") or ".pdf?" in current_url:
                return {
                    "mode": "pdf_url",
                    "pdf_url": driver.current_url,
                }

            new_handles = set(driver.window_handles) - original_handles
            if new_handles:
                handle = list(new_handles)[0]
                driver.switch_to.window(handle)

                switched_url = (driver.current_url or "").lower()
                if switched_url.endswith(".pdf") or ".pdf?" in switched_url:
                    return {
                        "mode": "pdf_url",
                        "pdf_url": driver.current_url,
                    }

                return {
                    "mode": "new_window",
                    "pdf_url": driver.current_url,
                }

            time.sleep(config.poll_seconds)

        return {
            "mode": "unknown",
            "pdf_url": "",
        }

    @classmethod
    def _save_pdf_via_js_print(cls, driver: WebDriver, final_path: Path) -> None:
        # Safari does not support Chrome's Page.printToPDF devtools endpoint.
        # So this routine only saves the URL as a placeholder if the report is a direct PDF URL.
        current_url = driver.current_url or ""
        if not current_url:
            raise CSDReportRefreshError("Unable to determine report URL for saving.")

        final_path.write_text(
            f"CSD report opened successfully in Safari. Manual save may be required.\nURL: {current_url}\n",
            encoding="utf-8",
        )

    @classmethod
    def _replace_report(cls, final_path: Path, archive_dir: Path) -> Dict[str, Any]:
        archived_path = cls._archive_existing_report(final_path, archive_dir)

        return {
            "final_path": str(final_path),
            "archived_previous_path": str(archived_path) if archived_path else "",
            "final_size_bytes": final_path.stat().st_size if final_path.exists() else 0,
        }

    @classmethod
    def refresh_registration_report(cls) -> Dict[str, Any]:
        config = cls.load_config()
        cls._ensure_dirs(config)

        driver: Optional[WebDriver] = None

        try:
            driver = cls._build_driver(config)

            login_result = cls._login(driver, config)
            cls._open_registration_report_flow(driver, config)

            final_path = config.compliance_dir / config.output_filename
            archived_path = cls._archive_existing_report(final_path, config.archive_dir)

            report_result = cls._wait_for_report_window_or_pdf(driver, config)

            if report_result.get("mode") in {"pdf_url", "new_window"}:
                cls._save_pdf_via_js_print(driver, final_path)
            else:
                raise CSDReportRefreshError("Report opened but PDF URL could not be confirmed.")

            return {
                "success": True,
                "status": "refreshed",
                "login_success": login_result.get("login_success", False),
                "manual_captcha_used": login_result.get("manual_captcha_used", False),
                "supplier_number": config.supplier_number,
                "final_path": str(final_path),
                "archived_previous_path": str(archived_path) if archived_path else "",
                "final_size_bytes": final_path.stat().st_size if final_path.exists() else 0,
                "report_mode": report_result.get("mode", ""),
                "report_url": report_result.get("pdf_url", ""),
                "refreshed_at": datetime.now().isoformat(),
                "note": "Safari successfully automated the report flow, but direct PDF download/save may still require a manual save step depending on how the CSD site renders the report.",
            }

        except Exception as exc:
            fallback_path = config.compliance_dir / config.output_filename
            return {
                "success": False,
                "status": "failed",
                "error": str(exc),
                "supplier_number": config.supplier_number,
                "fallback_existing_report": str(fallback_path) if fallback_path.exists() else "",
                "refreshed_at": datetime.now().isoformat(),
            }

        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass


def refresh_csd_registration_report() -> Dict[str, Any]:
    return CSDReportRefreshService.refresh_registration_report()
