from datetime import date, datetime

import pytest

from rvcadence.times import to_day_offsets

SEASON_START = date(2026, 5, 1)


def test_dates():
    assert to_day_offsets([date(2026, 5, 1), date(2026, 5, 11)], SEASON_START) == [0, 10]


def test_datetimes_round_to_the_nearest_day():
    assert to_day_offsets(
        [datetime(2026, 5, 3, 2, 0), datetime(2026, 5, 3, 20, 0)], SEASON_START
    ) == [2, 3]


def test_iso_strings():
    assert to_day_offsets(["2026-05-01", "2026-05-06T03:00:00"], SEASON_START) == [0, 5]


def test_jd_above_the_split():
    # 2026-05-01T00:00:00 UTC is JD 2461161.5.
    assert to_day_offsets([2461161.5, 2461171.5], SEASON_START) == [0, 10]


def test_mjd_below_the_split():
    # MJD = JD - 2400000.5, so 2026-05-01T00:00:00 UTC is MJD 61161.0.
    assert to_day_offsets([61161.0, 61171.0], SEASON_START) == [0, 10]


def test_rjd_needs_an_explicit_time_format():
    # RJD = JD - 2400000.0, so 2026-05-01T06:00:00 UTC is RJD 61161.75.
    # Read as MJD instead, the same number reconstructs a JD half a day LATER,
    # so the epoch lands on the following day. The 06:00 epochs matter: at
    # exact midnight the offsets are 0.5 and round() breaks ties to even, so
    # both readings would collapse to the same answer and prove nothing.
    rjd = [61161.75, 61171.75]
    assert to_day_offsets(rjd, SEASON_START, time_format="rjd") == [0, 10]
    assert to_day_offsets(rjd, SEASON_START) == [1, 11]


def test_time_format_override_jd_and_mjd():
    assert to_day_offsets([2461161.5], SEASON_START, time_format="jd") == [0]
    assert to_day_offsets([61161.0], SEASON_START, time_format="mjd") == [0]


def test_unknown_time_format_raises():
    with pytest.raises(ValueError, match="time_format must be"):
        to_day_offsets([61161.0], SEASON_START, time_format="hjd")


def test_epochs_before_season_start_give_negative_offsets():
    assert to_day_offsets([date(2026, 4, 21)], SEASON_START) == [-10]


def test_offsets_are_sorted_and_deduplicated():
    assert to_day_offsets(
        [date(2026, 5, 11), date(2026, 5, 1), date(2026, 5, 11)], SEASON_START
    ) == [0, 10]


def test_scalar_input_raises():
    with pytest.raises(TypeError, match="must be a sequence of epochs"):
        to_day_offsets(date(2026, 5, 1), SEASON_START)


def test_empty_input():
    assert to_day_offsets([], SEASON_START) == []
