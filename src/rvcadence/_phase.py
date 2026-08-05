from __future__ import annotations


def circ_dist_01(a: float, b: float) -> float:
    """Circular distance between two phases in [0, 1), wrapping at the boundary."""
    d = abs(a - b) % 1.0
    return min(d, 1.0 - d)


def min_phase_separation(phase: float, phases: list[float]) -> float:
    """Minimum circular phase distance in [0, 0.5] from `phase` to any in `phases`."""
    if not phases:
        return 0.5
    return min(circ_dist_01(phase, p) for p in phases)


def min_time_separation(t: int, times: list[int]) -> float:
    """Minimum absolute day distance from `t` to any in `times`."""
    if not times:
        return float("inf")
    return float(min(abs(t - x) for x in times))


def max_phase_gap(offsets: list[int], period_d: float) -> float:
    """
    Largest gap between consecutive phases when `offsets` are folded on
    `period_d`, measured around the full [0, 1) circle. 1.0 for fewer than
    two epochs, and the value falls as coverage improves.
    """
    phases = sorted((o % period_d) / period_d for o in offsets)
    if len(phases) < 2:
        return 1.0
    gaps = [b - a for a, b in zip(phases, phases[1:])]
    gaps.append(1.0 - phases[-1] + phases[0])
    return max(gaps)
