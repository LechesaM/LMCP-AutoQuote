from __future__ import annotations

from pathlib import Path

from app.services.tender_harvester import run_generic_scraper


def test_run_generic_scraper_reads_local_file_source(tmp_path: Path) -> None:
    html = tmp_path / "source.html"
    html.write_text(
        """
        <html>
          <body>
            <table>
              <tr><td>RFQ 1001 Supply and delivery of office supplies for 12 months</td><td>Closing date 2026-07-01</td></tr>
            </table>
          </body>
        </html>
        """.strip(),
        encoding="utf-8",
    )

    results = run_generic_scraper(
        {
            "name": "Local Test Source",
            "type": "generic_portal",
            "url": html.as_uri(),
        },
        max_items=5,
    )

    assert results
    assert results[0]["title"]
    assert "RFQ 1001" in results[0]["title"]
