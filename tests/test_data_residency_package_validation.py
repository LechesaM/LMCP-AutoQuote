from scripts.validate_data_residency_package import (
    test_no_live_or_autonomous_data_movement,
    test_required_files_exist,
    test_service_contains_required_governance_terms,
)


def test_data_residency_package_validator_passes() -> None:
    test_required_files_exist()
    test_service_contains_required_governance_terms()
    test_no_live_or_autonomous_data_movement()
