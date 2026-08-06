from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

_JD_MJD_SPLIT = 2.4e6
_MJD_OFFSET = 2400000.5
_RJD_OFFSET = 2400000.0
_JD_UNIX_EPOCH = 2440587.5  # JD at 1970-01-01T00:00:00 UTC
_UNIX_EPOCH_DATE = date(1970, 1, 1)
_TIME_COLUMN_NAMES = ("time", "bjd", "jd", "mjd", "date")
_TIME_FORMATS = ("jd", "mjd", "rjd")


def to_day_offsets(
    times: Any,
    season_start: date,
    time_format: str | None = None,
    time_column: str | None = None,
) -> list[int]:
    """
    Convert observation epochs to sorted, unique integer day offsets from
    `season_start`. Epochs before `season_start` give negative offsets.

    Accepts a sequence of `datetime.date`/`datetime.datetime`, ISO-8601
    strings, or floats; an `astropy.time.Time`; an `astropy.table.Column`; or
    an `astropy.table.Table` whose time column is auto-selected from
    time/bjd/jd/mjd/date (case-insensitive) unless `time_column` names one.
    Timezone-aware strings and `datetime` values are converted to UTC before
    the offset is computed.

    Bare floats above 2.4e6 are read as JD, at or below it as MJD.
    `time_format` overrides that heuristic with "jd", "mjd", or "rjd"
    (JD - 2400000.0).

    MJD and RJD are numerically indistinguishable: in 2026 both are near
    61000 and they differ by only 0.5 d, so no magnitude test can separate
    them. Read as MJD, an RJD number reconstructs a JD half a day later than
    the true epoch, so it can land on the following day. RJD input must
    declare itself.

    Multiple epochs on the same night collapse to one offset: a night is the
    scheduler's unit.
    """
    if time_format is not None and time_format not in _TIME_FORMATS:
        raise ValueError(f"time_format must be one of {_TIME_FORMATS}, got {time_format!r}")
    values, forced_format = _extract_values(times, time_column)
    fmt = forced_format or time_format
    return sorted({round(_offset_days(v, season_start, fmt)) for v in values})


def _offset_days(value: Any, season_start: date, time_format: str | None) -> float:
    """Fractional day offset of one epoch from midnight at the start of `season_start`."""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        midnight = datetime(season_start.year, season_start.month, season_start.day)
        return (value - midnight).total_seconds() / 86400.0
    if isinstance(value, date):
        return float((value - season_start).days)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.endswith("Z"):
            stripped = stripped[:-1] + "+00:00"
        return _offset_days(datetime.fromisoformat(stripped), season_start, time_format)
    jd_season_start = _JD_UNIX_EPOCH + (season_start - _UNIX_EPOCH_DATE).days
    return _to_jd(value, time_format) - jd_season_start


def _to_jd(value: Any, time_format: str | None) -> float:
    """Julian Date of one numeric epoch, from an explicit format or the magnitude heuristic."""
    x = float(value)
    if time_format == "jd":
        return x
    if time_format == "mjd":
        return x + _MJD_OFFSET
    if time_format == "rjd":
        return x + _RJD_OFFSET
    return x if x > _JD_MJD_SPLIT else x + _MJD_OFFSET


def _extract_values(times: Any, time_column: str | None) -> tuple[list[Any], str | None]:
    """
    Flatten an accepted container into (per-epoch values, forced time format).
    The forced format is "jd" for an astropy Time, which is read via `.jd`.
    """
    if isinstance(times, (str, bytes, date, datetime, float, int)):
        raise TypeError(
            "times must be a sequence of epochs (list, array, Column, Time or Table), "
            f"got a single {type(times).__name__}"
        )
    if type(times).__module__.split(".")[0] == "astropy":
        return _extract_astropy_values(times, time_column)
    return list(times), None


def _extract_astropy_values(times: Any, time_column: str | None) -> tuple[list[Any], str | None]:
    """Flatten an astropy Table, Time or Column. astropy is imported only on this path."""
    from astropy.table import Column, Table
    from astropy.time import Time

    if isinstance(times, Table):
        return _extract_values(times[_select_time_column(times, time_column)], None)
    if isinstance(times, Time):
        return [float(x) for x in times.jd.reshape(-1)], "jd"
    if isinstance(times, Column):
        return list(times), None
    return list(times), None


def _select_time_column(table: Any, time_column: str | None) -> str:
    """Name of the column holding the epochs, chosen explicitly or by convention."""
    names = list(table.colnames)
    if time_column is not None:
        if time_column not in names:
            raise ValueError(f"time_column {time_column!r} is not in the table columns {names}")
        return time_column
    matches = [c for c in names if c.strip().lower() in _TIME_COLUMN_NAMES]
    if not matches:
        raise ValueError(
            f"no time column found in {names}; expected one of "
            f"{list(_TIME_COLUMN_NAMES)} (case-insensitive), or pass time_column="
        )
    if len(matches) > 1:
        raise ValueError(
            f"several candidate time columns found: {matches}; pass time_column= to choose one"
        )
    return matches[0]
