from scripts.validate_final_governance_release_package import (
    test_no_live_or_autonomous_final_release_paths,
    test_required_files_exist,
    test_service_contains_required_governance_terms,
)


def test_final_governance_release_package_validator_passes() -> None:
    test_required_files_exist()
    test_service_contains_required_governance_terms()
    test_no_live_or_autonomous_final_release_paths()
