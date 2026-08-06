from __future__ import annotations

from datetime import date, timedelta

import astropy.units as u
from astropy.coordinates import EarthLocation, SkyCoord, get_body
from astropy.time import Time


def _local_midnight_utc(night: date, observer_location: EarthLocation) -> Time:
    """
    UTC Time of local solar midnight for the observing night labeled `night`.

    Nights are sunset-labeled (standard observatory convention): the night of
    `night` runs from sunset on `night` to sunrise on `night + 1 day`, so its
    local solar midnight falls in the early UTC hours of `night + 1 day`, not
    `night` itself.
    """
    lon_deg = observer_location.lon.deg
    midnight_utc_offset_h = (-lon_deg / 15.0) % 24.0
    t0 = Time((night + timedelta(days=1)).isoformat() + " 00:00:00")
    return t0 + midnight_utc_offset_h * u.hour


def moon_coord_at_midnight(night: date, observer_location: EarthLocation) -> SkyCoord:
    """Moon's apparent position at local solar midnight on `night`, from observer_location."""
    t = _local_midnight_utc(night, observer_location)
    return get_body("moon", t, observer_location)


def is_moon_polluted(
    night: date,
    target_coord: SkyCoord,
    observer_location: EarthLocation,
    min_sep_deg: float = 30.0,
) -> bool:
    """True if the Moon is within min_sep_deg of target_coord at local midnight on `night`."""
    if not 0.0 <= min_sep_deg <= 180.0:
        raise ValueError(f"min_sep_deg must be within [0, 180], got {min_sep_deg}")
    moon_coord = moon_coord_at_midnight(night, observer_location)
    # Evaluate the separation in the Moon's own observer-centric frame, which is
    # the apparent angle on the sky from the telescope. The direction is not a
    # detail: the Moon is close enough that comparing in the target's ICRS frame
    # instead answers a different question and can differ by tens of degrees.
    target_same_frame = target_coord.transform_to(moon_coord.frame)
    return bool(moon_coord.separation(target_same_frame).deg < min_sep_deg)


def moon_allowed_offsets(
    season_start: date,
    season_end: date,
    target_coord: SkyCoord,
    observer_location: EarthLocation,
    min_sep_deg: float = 30.0,
) -> list[int]:
    """Day offsets from season_start where the Moon is NOT within min_sep_deg of target_coord."""
    n_days = (season_end - season_start).days + 1
    allowed = []
    for k in range(n_days):
        night = season_start + timedelta(days=k)
        if not is_moon_polluted(night, target_coord, observer_location, min_sep_deg):
            allowed.append(k)
    return allowed
