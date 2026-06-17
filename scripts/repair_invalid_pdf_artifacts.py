from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _clean(value: str) -> str:
    return str(value or "").strip()


def _write_minimal_pdf(path: Path, lines: List[str]) -> None:
    safe_lines = [(_clean(line)[:120].replace("(", "[").replace(")", "]")) for line in lines if _clean(line)]
    if not safe_lines:
        safe_lines = [path.name]
    y = 170
    stream_lines = ["BT /F1 10 Tf"]
    for index, line in enumerate(safe_lines[:12]):
        offset = y - (index * 14)
        stream_lines.append(f"36 {offset} Td ({line}) Tj")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines)
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        f"4 0 obj\n<< /Length {len(stream.encode('utf-8'))} >>\nstream\n{stream}\nendstream\nendobj\n",
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    body = bytearray("%PDF-1.4\n".encode("utf-8"))
    offsets = [0]
    for obj in objects:
        offsets.append(len(body))
        body.extend(obj.encode("utf-8"))
    xref_offset = len(body)
    xref = ["xref\n0 6\n", "0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref.append(f"{offset:010d} 00000 n \n")
    trailer = f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    body.extend("".join(xref).encode("utf-8"))
    body.extend(trailer.encode("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(body))


def _read_json_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    lines: List[str] = []
    for key in ("tender_id", "quote_number", "title", "buyer_name", "status", "source", "package_status"):
        value = data.get(key)
        if value not in (None, ""):
            lines.append(f"{key}: {value}")
    return lines


def _pdf_lines_for(path: Path) -> List[str]:
    lines = [path.name]
    for sibling_name in (
        path.with_suffix(".json"),
        path.with_name(path.name.replace(".pdf", "__manifest.json")),
        path.with_name(path.name.replace(".pdf", ".json")),
    ):
        lines.extend(_read_json_lines(sibling_name))
    if "submission_receipt" in path.name:
        lines.append("submission receipt")
    if "quote_pack" in path.name:
        lines.append("quote pack")
    return lines


def repair_invalid_pdfs(root: Path) -> List[Path]:
    repaired: List[Path] = []
    for path in sorted(root.rglob("*.pdf")):
        try:
            head = path.read_bytes()[:4]
        except Exception:
            continue
        if head == b"%PDF":
            continue
        _write_minimal_pdf(path, _pdf_lines_for(path))
        repaired.append(path)
    return repaired


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Repair invalid PDF artifacts in the runtime tree.")
    parser.add_argument(
        "--root",
        type=Path,
        default=PROJECT_ROOT / "runtime" / "manual_production",
        help="Runtime root to scan.",
    )
    args = parser.parse_args(argv)
    repaired = repair_invalid_pdfs(args.root)
    if repaired:
        print("repaired pdf artifacts:")
        for path in repaired:
            print(f"- {path.relative_to(args.root)}")
        return 0
    print("no invalid pdf artifacts found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
