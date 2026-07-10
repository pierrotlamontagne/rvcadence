from __future__ import annotations

from datetime import date, timedelta

import astropy.units as u
import numpy as np
from astropy.coordinates import AltAz, EarthLocation, SkyCoord, get_sun
from astropy.time import Time

from .moon import _local_midnight_utc

_SIDEREAL_TO_SOLAR_HOUR_RATIO = 1.0027379093
_NIGHT_SAMPLE_HALF_WINDOW_MIN = 12 * 60
_NIGHT_SAMPLE_STEP_MIN = 15


def target_transit_time(night: date, target_coord: SkyCoord, observer_location: EarthLocation) -> Time:
    """
    UTC time of the target's transit (upper culmination) nearest to the
    local solar midnight of the observing night `night` (sunset-labeled:
    night `night` runs sunset(night)..sunrise(night + 1 day), same
    convention as moon.py's `_local_midnight_utc`). Standalone utility —
    not used by is_visible()'s own check (see below), kept for reporting/
    plotting use cases (e.g. altitude-at-transit calendar figures).
    """
    t_midnight = _local_midnight_utc(night, observer_location)
    lst_at_midnight = t_midnight.sidereal_time("apparent", longitude=observer_location.lon)
    hour_angle_at_midnight = (lst_at_midnight - target_coord.ra).wrap_at(180 * u.deg)
    solar_hours_to_transit = -hour_angle_at_midnight.hour / _SIDEREAL_TO_SOLAR_HOUR_RATIO
    return t_midnight + solar_hours_to_transit * u.hour


def _night_sample_times(night: date, observer_location: EarthLocation) -> Time:
    """
    Time array spanning local-midnight(night) +/- 12h, sampled every
    _NIGHT_SAMPLE_STEP_MIN minutes. This window fully contains the
    observing night `night` (sunset(night)..sunrise(night + 1 day)) with
    several hours of daytime margin on each side, regardless of season or
    latitude, without needing to compute sunset/sunrise explicitly.
    """
    t_midnight = _local_midnight_utc(night, observer_location)
    offsets_min = np.linspace(-_NIGHT_SAMPLE_HALF_WINDOW_MIN, _NIGHT_SAMPLE_HALF_WINDOW_MIN,
                               2 * _NIGHT_SAMPLE_HALF_WINDOW_MIN // _NIGHT_SAMPLE_STEP_MIN + 1)
    return t_midnight + offsets_min * u.minute


def is_visible(
    night: date,
    target_coord: SkyCoord,
    observer_location: EarthLocation,
    min_altitude_deg: float = 30.0,
    twilight_sun_alt_deg: float = -18.0,
) -> bool:
    """
    True if there is ANY instant during the observing night `night` at
    which the target is simultaneously at or above min_altitude_deg AND the
    Sun is at or below twilight_sun_alt_deg (astronomically dark). Sampled
    every 15 minutes across the full night, not evaluated only at the
    target's transit time — a target transiting during twilight can still
    be observable for hours once the sky is fully dark, so a transit-only
    check would silently under-count visible nights (group-meeting finding
    [M1], see this task's header note).

    First call in a process may trigger a one-time network download of
    IERS Earth-orientation tables (needed for precise sidereal time) —
    expected, not a bug, same as moon.py's existing note.
    """
    times = _night_sample_times(night, observer_location)
    frame = AltAz(obstime=times, location=observer_location)
    target_alt = target_coord.transform_to(frame).alt.deg
    sun_alt = get_sun(times).transform_to(frame).alt.deg
    return bool(np.any((target_alt >= min_altitude_deg) & (sun_alt <= twilight_sun_alt_deg)))


def visibility_allowed_offsets(
    season_start: date,
    season_end: date,
    target_coord: SkyCoord,
    observer_location: EarthLocation,
    min_altitude_deg: float = 30.0,
    twilight_sun_alt_deg: float = -18.0,
) -> list[int]:
    """Day offsets from season_start where is_visible() is True."""
    n_days = (season_end - season_start).days + 1
    allowed = []
    for k in range(n_days):
        night = season_start + timedelta(days=k)
        if is_visible(night, target_coord, observer_location, min_altitude_deg, twilight_sun_alt_deg):
            allowed.append(k)
    return allowed
