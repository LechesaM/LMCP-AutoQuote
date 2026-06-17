from __future__ import annotations

import gzip
import os
import subprocess
from pathlib import Path


SCRIPT_PATH = Path("/Users/cash/Documents/scripts/ops/backup_database.sh")


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _run_backup_script(tmp_path: Path, *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", str(SCRIPT_PATH), "20260524_123456"],
        cwd="/Users/cash/Documents",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_backup_database_prefers_docker_when_available(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        bin_dir / "docker",
        """#!/bin/sh
set -eu
if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
  exit 0
fi
if [ "${1:-}" = "info" ]; then
  exit 0
fi
if [ "${1:-}" = "compose" ] && [ "${2:-}" = "exec" ]; then
  shift 6
  sh -lc "$1"
  exit 0
fi
exit 1
""",
    )
    _write_executable(
        bin_dir / "pg_dump",
        """#!/bin/sh
printf 'DOCKER_PGDUMP\\n'
""",
    )

    backups_dir = tmp_path / "backups"
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["LMCP_BACKUP_DIR"] = str(backups_dir)

    result = _run_backup_script(tmp_path, env=env)

    assert result.returncode == 0, result.stderr
    out_dir = Path(result.stdout.strip())
    archive = out_dir / "database.sql.gz"
    manifest = out_dir / "database_backup_manifest.json"
    assert archive.exists()
    assert manifest.exists()
    assert "DOCKER_PGDUMP" in gzip.decompress(archive.read_bytes()).decode("utf-8")


def test_backup_database_falls_back_to_local_pg_dump_when_docker_unavailable(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        bin_dir / "docker",
        """#!/bin/sh
exit 1
""",
    )
    _write_executable(
        bin_dir / "pg_dump",
        """#!/bin/sh
printf 'LOCAL_PGDUMP\\n'
""",
    )

    backups_dir = tmp_path / "backups"
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["LMCP_BACKUP_DIR"] = str(backups_dir)
    env["DATABASE_URL"] = "postgresql://lmcp:secret@localhost:5432/lmcp_autoquote"

    result = _run_backup_script(tmp_path, env=env)

    assert result.returncode == 0, result.stderr
    out_dir = Path(result.stdout.strip())
    archive = out_dir / "database.sql.gz"
    manifest = out_dir / "database_backup_manifest.json"
    assert archive.exists()
    assert manifest.exists()
    assert "LOCAL_PGDUMP" in gzip.decompress(archive.read_bytes()).decode("utf-8")
    assert '"database": "lmcp_autoquote"' in manifest.read_text(encoding="utf-8")


def test_backup_database_reports_clear_remediation_when_neither_path_works(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        bin_dir / "docker",
        """#!/bin/sh
exit 1
""",
    )
    _write_executable(
        bin_dir / "pg_dump",
        """#!/bin/sh
exit 1
""",
    )

    backups_dir = tmp_path / "backups"
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["LMCP_BACKUP_DIR"] = str(backups_dir)

    result = _run_backup_script(tmp_path, env=env)

    assert result.returncode != 0
    assert "Database backup requires a ready Docker daemon" in result.stderr
    assert "Remediation:" in result.stderr
