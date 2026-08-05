from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import median
from typing import TYPE_CHECKING, Any, Sequence

from ._phase import min_phase_separation, min_time_separation
from .times import to_day_offsets
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


_DEFAULT_WEIGHTS_ROTATION = (0.55, 0.30, 0.15)
_DEFAULT_WEIGHTS_NO_ROTATION = (0.80, 0.20)


def _validate_weights(
    weights: Sequence[float] | None, has_rotation: bool
) -> tuple[float, float, float]:
    """
    Resolve the score weights to a (w_planet, w_rotation, w_time) triple. The
    rotation entry is 0.0 when no rotation period is known, in which case
    `weights` is a 2-element (w_planet, w_time) sequence.
    """
    if weights is None:
        if has_rotation:
            return _DEFAULT_WEIGHTS_ROTATION
        w_p, w_t = _DEFAULT_WEIGHTS_NO_ROTATION
        return (w_p, 0.0, w_t)

    w = [float(x) for x in weights]
    expected = 3 if has_rotation else 2
    if len(w) != expected:
        names = "(w_planet, w_rotation, w_time)" if has_rotation else "(w_planet, w_time)"
        state = "is given" if has_rotation else "is absent"
        raise ValueError(
            f"weights must have {expected} entries {names} when the rotation period "
            f"{state}, got {len(w)}"
        )
    # NaN must be rejected explicitly: every comparison against it is False,
    # so the sign and sum checks below would both pass it through, and a NaN
    # score then loses every `>` comparison in best_candidate.
    if any(math.isnan(x) for x in w):
        raise ValueError(f"weights must be finite, got {w}")
    if any(x < 0 for x in w):
        raise ValueError(f"weights must be non-negative, got {w}")
    if abs(sum(w) - 1.0) > 1e-6:
        raise ValueError(f"weights must sum to 1, got {sum(w)}")
    return (w[0], w[1], w[2]) if has_rotation else (w[0], 0.0, w[1])


def _validate_planet_weights(
    planet_weights: Sequence[float] | None, n_periods: int
) -> list[float] | None:
    """Validated per-planet priority weights, or None for worst-case (min) aggregation."""
    if planet_weights is None:
        return None
    w = [float(x) for x in planet_weights]
    if len(w) != n_periods:
        raise ValueError(
            f"planet_weights must have one entry per period ({n_periods}), got {len(w)}"
        )
    if any(math.isnan(x) for x in w):
        raise ValueError(f"planet_weights must be finite, got {w}")
    if any(x < 0 for x in w):
        raise ValueError(f"planet_weights must be non-negative, got {w}")
    if abs(sum(w) - 1.0) > 1e-6:
        raise ValueError(f"planet_weights must sum to 1, got {sum(w)}")
    return w


def evaluate_candidate(
    t: int,
    selected: list[int],
    periods_d: float | Sequence[float],
    p_rot_d: float,
    baseline_days: int,
    weights: Sequence[float] | None = None,
    planet_weights: Sequence[float] | None = None,
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

    `weights` overrides the default score weights. With a rotation period it
    is (w_planet, w_rotation, w_time); without one it is (w_planet, w_time).
    Entries must be non-negative and sum to 1. Defaults are (0.55, 0.30, 0.15)
    and (0.80, 0.20) respectively.

    `planet_weights` switches the planet-phase term from worst-case (min)
    aggregation to a priority-weighted mean over the periods. Entries must be
    non-negative and sum to 1, one per period. The weighted mean of values in
    [0, 0.5] stays in [0, 0.5], so it remains comparable to the rotation term.
    A high-weight, well-covered planet can mask a low-weight, poorly-covered
    one; that is the guarantee traded away by opting in.
    """
    if baseline_days <= 0:
        raise ValueError(f"baseline_days must be positive, got {baseline_days}")
    periods = _coerce_periods(periods_d)
    d_p_each = [
        min_phase_separation((t % p) / p, [(x % p) / p for x in selected])
        for p in periods
    ]
    pw = _validate_planet_weights(planet_weights, len(periods))
    d_p = min(d_p_each) if pw is None else sum(w * d for w, d in zip(pw, d_p_each))

    has_rotation = not math.isnan(p_rot_d) and p_rot_d > 0
    d_r = 0.0
    if has_rotation:
        phases_r = [(x % p_rot_d) / p_rot_d for x in selected]
        phase_r_t = (t % p_rot_d) / p_rot_d
        d_r = min_phase_separation(phase_r_t, phases_r)

    # Separations longer than the season carry no extra information: an epoch
    # far outside the planning window imposes no clustering penalty anywhere
    # in it. min_time_separation is non-negative, so only the upper bound bites.
    d_t = min(min_time_separation(t, selected) / baseline_days, 1.0)

    w_p, w_r, w_t = _validate_weights(weights, has_rotation)
    score = w_p * d_p + w_r * d_r + w_t * d_t

    return CandidateScore(t=t, d_p=d_p, d_r=d_r, d_t=d_t, score=score)


def best_candidate(
    candidates: list[int],
    selected: list[int],
    periods_d: float | Sequence[float],
    p_rot_d: float,
    baseline_days: int,
    min_gap_days: int = 1,
    weights: Sequence[float] | None = None,
    planet_weights: Sequence[float] | None = None,
) -> CandidateScore:
    """Highest-scoring feasible candidate not already selected or too close to one that is."""
    best: CandidateScore | None = None
    for t in candidates:
        if t in selected:
            continue
        if any(abs(t - s) < min_gap_days for s in selected):
            continue
        score = evaluate_candidate(t, selected, periods_d, p_rot_d, baseline_days, weights=weights, planet_weights=planet_weights)
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
    weights: Sequence[float] | None = None,
    planet_weights: Sequence[float] | None = None,
    existing_offsets: Sequence[int] | None = None,
) -> list[int]:
    """
    Greedily select day offsets to maximise phase coverage of the planet
    period(s) (and stellar rotation if known) while keeping observations
    temporally spread. Returns a sorted list of integer day offsets.

    `existing_offsets` are already-observed epochs. They are fixed for the
    whole run: they seed the greedy, they are never removed or re-scored, and
    they are excluded from the candidate pool. Only `n_obs - len(existing)`
    further offsets are chosen. Locked offsets outside `allowed_offsets` stay
    locked — constraints filter future candidates and cannot retroactively
    un-observe an epoch.
    """
    _coerce_periods(periods_d)  # validate eagerly, even if n_obs<=1 short-circuits below

    locked = sorted(set(int(x) for x in existing_offsets)) if existing_offsets else []
    if n_obs - len(locked) <= 0:
        return locked

    candidates = sorted(set(int(x) for x in allowed_offsets) - set(locked))
    if not candidates:
        raise ValueError("No candidate dates are available in provided observability windows.")

    if locked:
        selected = list(locked)
    else:
        if n_obs == 1:
            return [candidates[0]]
        if len(candidates) == 1:
            raise ValueError("Only one feasible candidate date exists but N_obs > 1.")
        selected = [candidates[0], candidates[-1]]

    while len(selected) < n_obs:
        selected.sort()
        best = best_candidate(
            candidates, selected, periods_d, p_rot_d, baseline_days,
            weights=weights, planet_weights=planet_weights,
        )
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
    """
    A planned calendar. `dates` is the sorted union of `locked_dates`
    (already observed, fixed) and `new_dates` (newly scheduled).

    `median_gap_d` and `mean_gap_d` are computed over the epochs falling
    within [season_start, season_end] only, so they always describe the
    cadence across the season being planned rather than the gap between an
    archive and the current season.
    """

    dates: list[date]
    median_gap_d: float
    mean_gap_d: float
    locked_dates: list[date] = field(default_factory=list)
    new_dates: list[date] = field(default_factory=list)
    n_remaining: int = 0


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
    weights: Sequence[float] | None = None,
    planet_weights: Sequence[float] | None = None,
    existing_times: Any = None,
    time_format: str | None = None,
    time_column: str | None = None,
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

    `existing_times` are epochs already observed. They are locked in place and
    only `n_obs - len(existing)` further dates are chosen. Accepts dates,
    ISO-8601 strings, JD/MJD floats, an astropy Time/Column/Table; see
    rvcadence.times.to_day_offsets for the format rules. RJD input must pass
    time_format="rjd" — MJD and RJD are numerically indistinguishable.
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

    existing_offsets = (
        to_day_offsets(existing_times, season_start, time_format, time_column)
        if existing_times is not None
        else []
    )
    offsets = build_schedule(
        n_obs, periods_d, p_rot, allowed, baseline_days,
        weights=weights, planet_weights=planet_weights,
        existing_offsets=existing_offsets,
    )

    locked = set(existing_offsets)
    dates = [season_start + timedelta(days=o) for o in offsets]
    locked_dates = [season_start + timedelta(days=o) for o in offsets if o in locked]
    new_dates = [season_start + timedelta(days=o) for o in offsets if o not in locked]

    if len(offsets) > n_obs:
        import warnings

        warnings.warn(
            f"{len(locked)} epochs were already observed but n_obs is {n_obs}; "
            f"returning the {len(offsets)} locked epochs and scheduling none",
            stacklevel=2,
        )

    in_season = [o for o in offsets if 0 <= o <= baseline_days]
    median_gap, mean_gap = spacing_stats(in_season)
    return ScheduleResult(
        dates=dates,
        median_gap_d=median_gap,
        mean_gap_d=mean_gap,
        locked_dates=locked_dates,
        new_dates=new_dates,
        n_remaining=max(0, n_obs - len(locked)),
    )
