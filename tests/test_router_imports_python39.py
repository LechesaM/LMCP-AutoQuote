from typing import get_type_hints


def test_rfq_lifecycle_upload_dry_run_annotation_is_python39_compatible():
    from app.api import rfq_lifecycle_api

    hints = get_type_hints(rfq_lifecycle_api.run_upload_dry_run_endpoint)
    assert "payload" in hints
