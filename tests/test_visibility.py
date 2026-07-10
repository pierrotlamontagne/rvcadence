from datetime import date

import numpy as np
import pytest

pytest.importorskip("astropy")

import astropy.units as u
from astropy.coordinates import AltAz, EarthLocation, SkyCoord, get_sun
from astropy.time import Time

from rvcadence.moon import _local_midnight_utc
from rvcadence.visibility import is_visible, target_transit_time, visibility_allowed_offsets

PARANAL = EarthLocation(lat=-24.6272 * u.deg, lon=-70.4039 * u.deg, height=2635 * u.m)
SIRIUS = SkyCoord(ra=101.28715533 * u.deg, dec=-16.71611586 * u.deg)
POLARIS = SkyCoord(ra=37.95456067 * u.deg, dec=89.26410897 * u.deg)


def test_target_transit_time_matches_known_geometry():
    # Independently verified (this session and during group-meeting review):
    # Sirius transits at Paranal on 2026-01-16 03:44:21 UTC with altitude
    # 82.11 deg and Sun altitude -41.6 deg, matching an independent
    # grid-scanned maximum to within 72 s.
    t = target_transit_time(date(2026, 1, 15), SIRIUS, PARANAL)
    assert abs((t - Time("2026-01-16T03:44:21")).sec) < 90
    frame = AltAz(obstime=t, location=PARANAL)
    assert abs(SIRIUS.transform_to(frame).alt.deg - 82.11) < 0.1
    assert abs(get_sun(t).transform_to(frame).alt.deg - (-41.6)) < 0.5


def test_always_visible_target_in_season():
    # Sirius is well clear of the Sun in January at Paranal: some part of
    # the night has it simultaneously above 30 deg and in astronomical dark.
    night = date(2026, 1, 15)
    assert is_visible(night, SIRIUS, PARANAL, min_altitude_deg=30.0, twilight_sun_alt_deg=-18.0) is True


def test_never_visible_target_negative_max_altitude():
    # Polaris (Dec +89.26 deg) at Paranal (lat -24.63 deg, southern
    # hemisphere): max possible altitude = 90 - |lat - dec| < 0, so it never
    # rises, on any date, at any (even 0 deg) altitude threshold, at any
    # time of night — grid-sampling can't rescue a target that never rises.
    night = date(2026, 1, 15)
    assert is_visible(night, POLARIS, PARANAL, min_altitude_deg=0.0, twilight_sun_alt_deg=-18.0) is False


def test_never_visible_target_shares_suns_ra_that_season():
    # Sirius and the Sun share RA in June: checked numerically (this
    # session) that Sirius is NOT above 30 deg and dark at ANY sampled time
    # that night, not just at transit -- a real astronomical exclusion
    # (conjunction with the Sun), not an artifact of evaluating only at
    # transit (which is exactly the bug group-meeting item [M1] flagged and
    # this grid-sampled rewrite fixes).
    night = date(2026, 6, 15)
    assert is_visible(night, SIRIUS, PARANAL, min_altitude_deg=30.0, twilight_sun_alt_deg=-18.0) is False


def test_never_visible_due_to_permanent_daylight_coincidence():
    # Construct a target at the Sun's own coordinates on this date: a fixed
    # sidereal point near the Sun's position stays close to the Sun for
    # nearby dates too, so it is never simultaneously up and dark -- queried
    # live rather than a hand-computed calendar fact.
    night = date(2026, 6, 15)
    sun_coord = get_sun(Time(f"{night.isoformat()}T12:00:00"))
    sun_like_target = SkyCoord(ra=sun_coord.ra, dec=sun_coord.dec)
    assert is_visible(night, sun_like_target, PARANAL, min_altitude_deg=0.0, twilight_sun_alt_deg=-18.0) is False


def test_altitude_threshold_boundary():
    # Compute the target's actual maximum sampled altitude during the night
    # directly (same 12h-half-window/15-min-step grid as is_visible's own
    # implementation, see Step 3) rather than importing an internal helper —
    # same "construct the boundary from known geometry" style as the
    # existing moon-separation boundary test's directional_offset_by usage.
    night = date(2026, 1, 15)
    times = _local_midnight_utc(night, PARANAL) + np.linspace(-12 * 60, 12 * 60, 97) * u.minute
    frame = AltAz(obstime=times, location=PARANAL)
    max_alt = SIRIUS.transform_to(frame).alt.deg.max()
    assert is_visible(night, SIRIUS, PARANAL, min_altitude_deg=max_alt - 2.0, twilight_sun_alt_deg=-18.0) is True
    assert is_visible(night, SIRIUS, PARANAL, min_altitude_deg=max_alt + 2.0, twilight_sun_alt_deg=-18.0) is False


def test_visibility_allowed_offsets_always_visible():
    allowed = visibility_allowed_offsets(date(2026, 1, 15), date(2026, 1, 17), SIRIUS, PARANAL)
    assert allowed == [0, 1, 2]


def test_visibility_allowed_offsets_never_visible():
    allowed = visibility_allowed_offsets(date(2026, 1, 15), date(2026, 1, 17), POLARIS, PARANAL)
    assert allowed == []
