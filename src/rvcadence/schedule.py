from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
from typing import TYPE_CHECKING, Sequence

from ._phase import min_phase_separation, min_time_separation
from .windows import build_allowed_offsets, parse_obs_windows

if TYPE_CHECKING:
    from astropy.coordinates import EarthLocation, SkyCoord


@dataclass
class CandidateScore:
    t: int
    d_p: float
    d_r: float
    d_t: float
    score: float


def _coerce_periods(periods_d: float | Sequence[float]) -> list[float]:
    periods = [periods_d] if isinstance(periods_d, (int, float)) else list(periods_d)
    if not periods:
        raise ValueError("periods_d must contain at least one period")
    for p in periods:
        if not p > 0:
            raise ValueError(f"periods_d must be positive, got {p}")
    return periods


def evaluate_candidate(
    t: int,
    selected: list[int],
    periods_d: float | Sequence[float],
    p_rot_d: float,
    baseline_days: int,
) -> CandidateScore:
    """
    Score one candidate day offset `t` against the currently `selected` days:
    weighted sum of planet-phase coverage, stellar-rotation-phase coverage
    (if p_rot_d is known), and temporal spread.

    `periods_d` accepts a single planet period (float) or multiple (a
    sequence, for multi-planet systems). With multiple periods, the
    planet-phase term is the worst-case (min) phase distance across all of
    them, not an average — a candidate only scores well if it improves
    coverage for whichever planet is currently least-covered.
    """
    if baseline_days <= 0:
        raise ValueError(f"baseline_days must be positive, got {baseline_days}")
    periods = _coerce_periods(periods_d)
    d_p = min(
        min_phase_separation(
            (t % p) / p, [(x % p) / p for x in selected]
        )
        for p in periods
    )

    has_rotation = not math.isnan(p_rot_d) and p_rot_d > 0
    d_r = 0.0
    if has_rotation:
        phases_r = [(x % p_rot_d) / p_rot_d for x in selected]
        phase_r_t = (t % p_rot_d) / p_rot_d
        d_r = min_phase_separation(phase_r_t, phases_r)

    d_t = min_time_separation(t, selected) / baseline_days

    if has_rotation:
        score = 0.55 * d_p + 0.30 * d_r + 0.15 * d_t
    else:
        score = 0.80 * d_p + 0.20 * d_t

    return CandidateScore(t=t, d_p=d_p, d_r=d_r, d_t=d_t, score=score)


def best_candidate(
    candidates: list[int],
    selected: list[int],
    periods_d: float | Sequence[float],
    p_rot_d: float,
    baseline_days: int,
    min_gap_days: int = 1,
) -> CandidateScore:
    """Highest-scoring feasible candidate not already selected or too close to one that is."""
    best: CandidateScore | None = None
    for t in candidates:
        if t in selected:
            continue
        if any(abs(t - s) < min_gap_days for s in selected):
            continue
        score = evaluate_candidate(t, selected, periods_d, p_rot_d, baseline_days)
        if best is None or score.score > best.score:
            best = score
    if best is None:
        raise RuntimeError(
            "Could not find feasible next observation time within observability windows. "
            "Try lowering N_obs or min_gap_days."
        )
    return best


def build_schedule(
    n_obs: int,
    periods_d: float | Sequence[float],
    p_rot_d: float,
    allowed_offsets: list[int],
    baseline_days: int,
) -> list[int]:
    """
    Greedily select n_obs day offsets from allowed_offsets to maximise phase
    coverage of the planet period(s) (and stellar rotation if known) while
    keeping observations temporally spread. Returns a sorted list of integer
    day offsets.
    """
    _coerce_periods(periods_d)  # validate eagerly, even if n_obs<=1 short-circuits below

    if n_obs <= 0:
        return []

    candidates = sorted(set(int(x) for x in allowed_offsets))
    if not candidates:
        raise ValueError("No candidate dates are available in provided observability windows.")
    if n_obs == 1:
        return [candidates[0]]
    if len(candidates) == 1:
        raise ValueError("Only one feasible candidate date exists but N_obs > 1.")

    selected = [candidates[0], candidates[-1]]
    while len(selected) < n_obs:
        selected.sort()
        best = best_candidate(candidates, selected, periods_d, p_rot_d, baseline_days)
        selected.append(best.t)

    selected.sort()
    return selected


def spacing_stats(times: list[int]) -> tuple[float, float]:
    """Return (median_gap, mean_gap) in days for a sorted list of day offsets."""
    if len(times) < 2:
        return math.nan, math.nan
    gaps = [float(times[i + 1] - times[i]) for i in range(len(times) - 1)]
    return median(gaps), sum(gaps) / len(gaps)


@dataclass
class ScheduleResult:
    dates: list[date]
    median_gap_d: float
    mean_gap_d: float


def plan_calendar(
    n_obs: int,
    periods_d: float | Sequence[float],
    season_start: date,
    season_end: date,
    rotation_period_d: float | None = None,
    windows: str | list[tuple[date, date]] = "",
    target_coord: "str | SkyCoord | None" = None,
    observer_location: "str | EarthLocation | None" = None,
    min_moon_sep_deg: float | None = 30.0,
    min_altitude_deg: float | None = None,
    twilight_sun_alt_deg: float = -18.0,
) -> ScheduleResult:
    """
    High-level entry point: plan an observing calendar directly in real dates.

    `windows` accepts either raw text ("2026-05-01 to 2026-08-18; ...") or an
    already-parsed list of (start, end) date tuples. `periods_d` accepts a
    single planet period (float) or multiple (a sequence, worst-case/min
    phase-coverage aggregation across periods).

    `target_coord`/`observer_location` accept either already-resolved
    astropy objects (SkyCoord/EarthLocation) or plain name strings (resolved
    once, via rvcadence.target, printing the resolved value). If given,
    nights are additionally restricted by:
      - moon avoidance: excluded if the Moon is within `min_moon_sep_deg` of
        the target at local midnight (skipped if min_moon_sep_deg is None).
      - visibility: excluded unless the target is at or above
        `min_altitude_deg` AND the Sun is at or below `twilight_sun_alt_deg`,
        both evaluated at the target's transit time that night (skipped if
        min_altitude_deg is None, the default — there is no universally
        correct altitude threshold).
    All supplied constraint types (windows / moon / visibility) intersect.
    """
    baseline_days = (season_end - season_start).days
    parsed_windows = parse_obs_windows(windows) if isinstance(windows, str) else windows
    allowed = build_allowed_offsets(season_start, season_end, parsed_windows)

    if target_coord is not None and observer_location is None:
        raise ValueError("observer_location is required when target_coord is given")
    if observer_location is not None and target_coord is None:
        raise ValueError("target_coord is required when observer_location is given")

    if target_coord is not None:
        if isinstance(target_coord, str) or isinstance(observer_location, str):
            from .target import resolve_site_name, resolve_target_name

            if isinstance(target_coord, str):
                target_coord = resolve_target_name(target_coord)
            if isinstance(observer_location, str):
                observer_location = resolve_site_name(observer_location)

        if min_moon_sep_deg is not None:
            from .moon import moon_allowed_offsets

            moon_allowed = set(
                moon_allowed_offsets(season_start, season_end, target_coord, observer_location, min_moon_sep_deg)
            )
            allowed = [o for o in allowed if o in moon_allowed]

        if min_altitude_deg is not None:
            from .visibility import visibility_allowed_offsets

            vis_allowed = set(
                visibility_allowed_offsets(
                    season_start, season_end, target_coord, observer_location,
                    min_altitude_deg, twilight_sun_alt_deg,
                )
            )
            allowed = [o for o in allowed if o in vis_allowed]

    p_rot = rotation_period_d if rotation_period_d is not None else math.nan
    offsets = build_schedule(n_obs, periods_d, p_rot, allowed, baseline_days)

    dates = [season_start + timedelta(days=o) for o in offsets]
    median_gap, mean_gap = spacing_stats(offsets)
    return ScheduleResult(dates=dates, median_gap_d=median_gap, mean_gap_d=mean_gap)
