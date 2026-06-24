from scripts.validate_compliance_regulatory_package import (
    test_no_live_or_autonomous_regulatory_controls,
    test_required_files_exist,
    test_service_contains_required_governance_terms,
)


def test_compliance_regulatory_package_validator_passes() -> None:
    test_required_files_exist()
    test_service_contains_required_governance_terms()
    test_no_live_or_autonomous_regulatory_controls()
