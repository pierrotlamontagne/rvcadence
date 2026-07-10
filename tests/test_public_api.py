def test_core_api_importable_without_astropy():
    import rvcadence

    for name in [
        "parse_obs_windows", "build_allowed_offsets", "contiguous_ranges",
        "CandidateScore", "evaluate_candidate", "best_candidate",
        "build_schedule", "spacing_stats", "ScheduleResult", "plan_calendar",
    ]:
        assert hasattr(rvcadence, name), f"rvcadence.{name} missing"


def test_moon_api_exposed_when_astropy_available():
    import pytest
    pytest.importorskip("astropy")
    import rvcadence

    for name in ["is_moon_polluted", "moon_allowed_offsets", "moon_coord_at_midnight"]:
        assert hasattr(rvcadence, name), f"rvcadence.{name} missing"


def test_visibility_and_target_api_exposed_when_astropy_available():
    import pytest
    pytest.importorskip("astropy")
    import rvcadence

    for name in [
        "resolve_target_name", "resolve_site_name",
        "target_transit_time", "is_visible", "visibility_allowed_offsets",
    ]:
        assert hasattr(rvcadence, name), f"rvcadence.{name} missing"
