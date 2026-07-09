from datetime import date

import pytest

pytest.importorskip("astropy")

import astropy.units as u
from astropy.coordinates import EarthLocation, SkyCoord

from rvcadence.moon import is_moon_polluted, moon_allowed_offsets, moon_coord_at_midnight

PARANAL = EarthLocation(lat=-24.6272 * u.deg, lon=-70.4039 * u.deg, height=2635 * u.m)


def test_is_moon_polluted_true_when_target_is_the_moon():
    night = date(2026, 6, 1)
    moon_coord = moon_coord_at_midnight(night, PARANAL)
    assert is_moon_polluted(night, moon_coord, PARANAL, min_sep_deg=30.0) is True


def test_is_moon_polluted_respects_threshold():
    night = date(2026, 6, 1)
    moon_coord = moon_coord_at_midnight(night, PARANAL)
    just_inside = moon_coord.directional_offset_by(0 * u.deg, 29.0 * u.deg)
    just_outside = moon_coord.directional_offset_by(0 * u.deg, 31.0 * u.deg)
    assert is_moon_polluted(night, just_inside, PARANAL, min_sep_deg=30.0) is True
    assert is_moon_polluted(night, just_outside, PARANAL, min_sep_deg=30.0) is False


def test_moon_allowed_offsets_excludes_the_polluted_night():
    season_start = date(2026, 6, 1)
    season_end = date(2026, 6, 3)
    moon_coord = moon_coord_at_midnight(season_start, PARANAL)
    allowed = moon_allowed_offsets(season_start, season_end, moon_coord, PARANAL, min_sep_deg=30.0)
    assert 0 not in allowed
    assert all(isinstance(o, int) and 0 <= o <= 2 for o in allowed)


def test_local_midnight_anchors_to_night_plus_one_day():
    # Nights are sunset-labeled: the night of `night` runs sunset(night) to
    # sunrise(night+1), so local solar midnight must fall on night+1's UTC
    # calendar date, not night's (group-meeting finding — see design doc).
    from rvcadence.moon import _local_midnight_utc

    night = date(2026, 6, 1)
    t = _local_midnight_utc(night, PARANAL)
    assert t.datetime.date() == date(2026, 6, 2)


def test_is_moon_polluted_rejects_out_of_range_min_sep_deg():
    night = date(2026, 6, 1)
    moon_coord = moon_coord_at_midnight(night, PARANAL)
    with pytest.raises(ValueError, match=r"min_sep_deg must be within \[0, 180\]"):
        is_moon_polluted(night, moon_coord, PARANAL, min_sep_deg=200.0)
    with pytest.raises(ValueError, match=r"min_sep_deg must be within \[0, 180\]"):
        is_moon_polluted(night, moon_coord, PARANAL, min_sep_deg=-5.0)
