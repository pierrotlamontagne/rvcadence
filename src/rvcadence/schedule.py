from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median
from typing import Sequence

from ._phase import min_phase_separation, min_time_separation


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
