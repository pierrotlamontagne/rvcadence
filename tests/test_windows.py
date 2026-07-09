from datetime import date

from rvcadence.windows import (
    build_allowed_offsets,
    contiguous_ranges,
    parse_date_yyyy_mm_dd,
    parse_obs_windows,
)


def test_parse_date_yyyy_mm_dd():
    assert parse_date_yyyy_mm_dd("2026-05-01") == date(2026, 5, 1)


def test_parse_obs_windows_single_range():
    assert parse_obs_windows("2026-05-01 to 2026-08-18") == [
        (date(2026, 5, 1), date(2026, 8, 18))
    ]


def test_parse_obs_windows_multiple_ranges():
    text = "2026-05-01 to 2026-08-18; 2026-12-19 to 2027-04-30"
    assert parse_obs_windows(text) == [
        (date(2026, 5, 1), date(2026, 8, 18)),
        (date(2026, 12, 19), date(2027, 4, 30)),
    ]


def test_parse_obs_windows_placeholders_return_empty():
    for placeholder in ["", "NA", "nan", "n/a", "none", "XXX", "TBD", "?"]:
        assert parse_obs_windows(placeholder) == []


def test_build_allowed_offsets_full_season_when_no_windows():
    offsets = build_allowed_offsets(date(2026, 1, 1), date(2026, 1, 5), [])
    assert offsets == [0, 1, 2, 3, 4]


def test_build_allowed_offsets_restricted_to_windows():
    windows = [(date(2026, 1, 3), date(2026, 1, 5))]
    offsets = build_allowed_offsets(date(2026, 1, 1), date(2026, 1, 10), windows)
    assert offsets == [2, 3, 4]


def test_build_allowed_offsets_raises_on_reversed_season():
    import pytest
    with pytest.raises(ValueError, match="is before season_start"):
        build_allowed_offsets(date(2026, 1, 10), date(2026, 1, 1), [])


def test_contiguous_ranges():
    assert contiguous_ranges([0, 1, 2, 5, 6, 9]) == [(0, 2), (5, 6), (9, 9)]


def test_contiguous_ranges_empty():
    assert contiguous_ranges([]) == []
