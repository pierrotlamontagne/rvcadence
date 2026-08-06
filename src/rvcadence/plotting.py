"""
Matplotlib figures for a ScheduleResult.

Not re-exported at package level;
import from here directly. Every function takes the result as its first
argument, draws into `ax` when given and creates its own figure otherwise,
and returns the Axes, so the figures compose.
"""

from __future__ import annotations

import math
from datetime import timedelta

import numpy as np

try:
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
except ImportError as exc:  # pragma: no cover - exercised only without matplotlib
    raise ImportError(
        "rvcadence.plotting requires matplotlib. Install it with: pip install matplotlib"
    ) from exc

from ._phase import max_phase_gap
from .schedule import ScheduleResult, build_schedule

_LOCKED_COLOR = "#fb8500"
_NEW_COLOR = "#023047"
_LOCKED_LABEL = "already observed"
_NEW_LABEL = "newly scheduled"
_PLANET_COLORS = ("#023047", "#d62828", "#2a9d8f", "#8338ec", "#ff006e")


def _new_ax(ax, figsize):
    """The supplied axes, or a fresh figure's axes at `figsize`."""
    return ax if ax is not None else plt.subplots(figsize=figsize)[1]


def _split_dates(result: ScheduleResult) -> tuple[list, list]:
    """(locked, new) date lists; every date counts as new when none are locked."""
    if result.locked_dates:
        return list(result.locked_dates), list(result.new_dates)
    return [], list(result.new_dates or result.dates)


def _offsets(dates, season_start) -> list[int]:
    """Day offsets of `dates` from `season_start`."""
    return [(d - season_start).days for d in dates]


def _date_axis(ax):
    """
    Label a date x-axis at whatever density fits. Spelling out every tick as
    an ISO date overruns the width of a season-long axis, so ticks carry the
    short form ("May", "Jun") and the year moves to an offset label.
    """
    locator = mdates.AutoDateLocator(minticks=3, maxticks=8)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    return ax


def plot_timeline(result: ScheduleResult, *, ax=None, windows=None):
    """Scheduled dates across the season, with the allowed windows shaded behind them."""
    ax = _new_ax(ax, (9, 2.0))
    locked, new = _split_dates(result)
    ax.set_xlim(result.season_start, result.season_end)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    for w_start, w_end in windows or []:
        ax.axvspan(w_start, w_end, color="#8ecae6", alpha=0.35, lw=0)
    if locked:
        ax.vlines(locked, 0, 1, color=_LOCKED_COLOR, lw=1.8, label=_LOCKED_LABEL)
    if new:
        ax.vlines(new, 0, 1, color=_NEW_COLOR, lw=1.2, label=_NEW_LABEL)
    _date_axis(ax)
    if locked:
        ax.legend(loc="upper right", fontsize=8)
    return ax


def plot_phase_coverage(result: ScheduleResult, *, ax=None):
    """Orbital phase of every scheduled epoch, one row per planet period."""
    periods = list(result.periods_d)
    ax = _new_ax(ax, (7, 0.9 + 0.6 * len(periods)))
    locked, new = _split_dates(result)
    for i, p in enumerate(periods):
        y = len(periods) - 1 - i
        for dates, color, label in (
            (locked, _LOCKED_COLOR, _LOCKED_LABEL),
            (new, _NEW_COLOR, _NEW_LABEL),
        ):
            if not dates:
                continue
            phases = [(o % p) / p for o in _offsets(dates, result.season_start)]
            ax.scatter(
                phases, [y] * len(phases), s=45, color=color, zorder=3,
                label=label if i == 0 else None,
            )
    ax.set_yticks(range(len(periods)))
    ax.set_yticklabels([f"P = {p:g} d" for p in reversed(periods)])
    ax.set_ylim(-0.5, len(periods) - 0.5)
    ax.set_xlim(0, 1)
    ax.set_xlabel("orbital phase")
    if locked:
        ax.legend(loc="upper right", fontsize=8)
    return ax


def _season_offsets(result: ScheduleResult) -> list[int]:
    """Every day offset in [season_start, season_end]."""
    return list(range((result.season_end - result.season_start).days + 1))


def plot_night_availability(result: ScheduleResult, *, ax=None, allowed_offsets=None):
    """
    Which nights pass the constraints (green strip) and which of them are
    scheduled. `allowed_offsets` is the pool the schedule was built from; the
    whole season is assumed when it is omitted.
    """
    ax = _new_ax(ax, (9, 1.8))
    n_days = (result.season_end - result.season_start).days + 1
    mask = np.zeros(n_days)
    for o in (allowed_offsets if allowed_offsets is not None else range(n_days)):
        if 0 <= o < n_days:
            mask[o] = 1.0
    ax.imshow(
        mask.reshape(1, -1), aspect="auto", cmap="Greens",
        vmin=0, vmax=1.6, extent=[0, n_days, 0, 1],
    )
    locked, new = _split_dates(result)
    for dates, color, label, marker in (
        (locked, _LOCKED_COLOR, _LOCKED_LABEL, "o"),
        (new, _NEW_COLOR, _NEW_LABEL, "*"),
    ):
        if not dates:
            continue
        idx = [o for o in _offsets(dates, result.season_start) if 0 <= o < n_days]
        if not idx:
            continue
        # Night o spans x in [o, o+1] in the imshow extent below, so the
        # marker sits at its midpoint rather than straddling the left edge.
        centers = [o + 0.5 for o in idx]
        ax.scatter(
            centers, [0.5] * len(centers), marker=marker, s=140, color=color,
            edgecolor="white", linewidth=0.6, zorder=3, label=label,
        )
    ax.set_yticks([])
    ax.set_xlabel(f"days since {result.season_start.isoformat()}")
    if locked:
        ax.legend(loc="upper right", fontsize=8)
    return ax


def plot_constraint_breakdown(result: ScheduleResult, *, ax=None, counts=None):
    """
    How many nights each constraint leaves, from a {label: n_nights} mapping,
    against the number of epochs the schedule needs.
    """
    if not counts:
        raise ValueError(
            "counts is required: a mapping of constraint label -> number of surviving nights"
        )
    ax = _new_ax(ax, (7, 3.0))
    labels = list(counts)
    values = [counts[k] for k in labels]
    ax.bar(range(len(labels)), values, color="#219ebc")
    for i, v in enumerate(values):
        ax.text(i, v, str(v), ha="center", va="bottom", fontsize=8)
    ax.axhline(
        len(result.dates), color="#d62828", ls="--", lw=1,
        label=f"{len(result.dates)} epochs scheduled",
    )
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("nights")
    ax.legend(fontsize=8)
    return ax


def plot_greedy_vs_random(
    result: ScheduleResult, *, ax=None, allowed_offsets=None, period_d=None, seed=42
):
    """
    Phase histogram of the schedule against the same number of nights drawn at
    random from the same pool — the sanity check on the greedy selection.
    """
    ax = _new_ax(ax, (7, 3.0))
    p = period_d if period_d is not None else result.periods_d[0]
    pool = sorted(allowed_offsets) if allowed_offsets is not None else _season_offsets(result)
    n = min(len(result.dates), len(pool))
    random_offsets = np.random.default_rng(seed).choice(pool, size=n, replace=False)

    greedy_phases = [(o % p) / p for o in _offsets(result.dates, result.season_start)]
    random_phases = [(int(o) % p) / p for o in random_offsets]
    bins = np.linspace(0, 1, 11)
    ax.hist(greedy_phases, bins=bins, color=_NEW_COLOR, alpha=0.8, label="greedy")
    ax.hist(
        random_phases, bins=bins, histtype="step", lw=1.6, color="#d62828",
        label="random, same night pool",
    )
    ax.set_xlabel("orbital phase")
    ax.set_ylabel("count")
    ax.legend(fontsize=8)
    return ax


def plot_phase_vs_rotation_phase(result: ScheduleResult, *, ax=None, period_d=None):
    """
    Orbital phase against stellar-rotation phase for the scheduled epochs.
    Points falling along a line mean the cadence aliases the planet signal onto
    the activity signal, so the two will be hard to separate in the RV fit.
    """
    if result.rotation_period_d is None:
        raise ValueError("plot_phase_vs_rotation_phase needs a rotation period on the result")
    ax = _new_ax(ax, (4.4, 4.4))
    p = period_d if period_d is not None else result.periods_d[0]
    p_rot = result.rotation_period_d
    locked, new = _split_dates(result)
    for dates, color, label in (
        (locked, _LOCKED_COLOR, _LOCKED_LABEL),
        (new, _NEW_COLOR, _NEW_LABEL),
    ):
        if not dates:
            continue
        offs = _offsets(dates, result.season_start)
        ax.scatter(
            [(o % p) / p for o in offs], [(o % p_rot) / p_rot for o in offs],
            s=45, color=color, zorder=3, label=label,
        )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel(f"orbital phase (P = {p:g} d)")
    ax.set_ylabel(f"rotation phase (P_rot = {p_rot:g} d)")
    if locked:
        ax.legend(fontsize=8)
    return ax


def plot_coverage_vs_n(result: ScheduleResult, *, ax=None, allowed_offsets=None, n_values=None):
    """
    Largest phase gap per planet as a function of how many epochs are
    scheduled -- the "how many observations do I actually need" curve. Each
    point re-runs the greedy from scratch on the same night pool.

    If `result` was built with window, moon, or visibility constraints, pass
    the same pool as `allowed_offsets` -- `ScheduleResult` does not store it,
    so without it the default pool is the full season and the curve's last
    point may not match the actual schedule's largest phase gap.
    """
    ax = _new_ax(ax, (6.5, 3.4))
    baseline_days = (result.season_end - result.season_start).days
    pool = sorted(allowed_offsets) if allowed_offsets is not None else _season_offsets(result)
    p_rot = result.rotation_period_d if result.rotation_period_d is not None else math.nan
    locked = _offsets(result.locked_dates, result.season_start) or None

    # Below the number of locked epochs there is nothing left to schedule,
    # so the curve starts where the greedy actually has a choice.
    first = max(2, len(result.locked_dates))
    if n_values is None:
        n_values = list(range(first, len(result.dates) + 1))
    else:
        # Same floor applies to caller-supplied values -- points below it
        # would all plot the identical locked-only schedule.
        n_values = [n for n in n_values if n >= first]
        if not n_values:
            raise ValueError(f"n_values must include at least one value >= {first}")

    # Re-runs the same optimization that produced this result -- same weights,
    # same locked epochs -- so the curve describes the schedule beside it.
    schedules = {
        n: build_schedule(
            n, result.periods_d, p_rot, pool, baseline_days,
            weights=result.weights, planet_weights=result.planet_weights,
            existing_offsets=locked,
        )
        for n in n_values
    }
    for p, color in zip(result.periods_d, _PLANET_COLORS):
        gaps = [max_phase_gap(schedules[n], p) for n in n_values]
        ax.plot(n_values, gaps, marker="o", color=color, label=f"P = {p:g} d")
    ax.set_xlabel("number of scheduled epochs")
    ax.set_ylabel("largest phase gap")
    ax.legend(fontsize=8)
    return ax


def plot_staralt(
    result: ScheduleResult,
    *,
    ax=None,
    target_coord=None,
    observer_location=None,
    min_altitude_deg=30.0,
    min_moon_sep_deg=30.0,
    twilight_sun_alt_deg=-18.0,
):
    """
    Airmass as a function of night and time-of-night, masked to the moments
    that are dark, above `min_altitude_deg`, and clear of the Moon.

    Passing `min_moon_sep_deg=None` disables the Moon check entirely, so
    every night is treated as Moon-clear.
    """
    if target_coord is None or observer_location is None:
        raise ValueError("target_coord and observer_location are required for plot_staralt")

    import astropy.units as u
    from astropy.coordinates import AltAz, get_sun

    from .moon import _local_midnight_utc, is_moon_polluted

    ax = _new_ax(ax, (9, 4.2))
    offsets = _season_offsets(result)
    nights = [result.season_start + timedelta(days=k) for k in offsets]
    minutes = np.linspace(-12 * 60, 12 * 60, 2 * 12 * 60 // 15 + 1)

    alt = np.full((len(nights), len(minutes)), np.nan)
    dark = np.zeros_like(alt, dtype=bool)
    moon_ok = np.zeros(len(nights), dtype=bool)

    for i, night in enumerate(nights):
        times = _local_midnight_utc(night, observer_location) + minutes * u.minute
        frame = AltAz(obstime=times, location=observer_location)
        alt[i] = target_coord.transform_to(frame).alt.deg
        dark[i] = get_sun(times).transform_to(frame).alt.deg <= twilight_sun_alt_deg
        moon_ok[i] = min_moon_sep_deg is None or not is_moon_polluted(
            night, target_coord, observer_location, min_sep_deg=min_moon_sep_deg
        )

    observable = dark & moon_ok[:, None] & (alt >= min_altitude_deg)
    with np.errstate(invalid="ignore", divide="ignore"):
        airmass = np.where(observable, 1.0 / np.sin(np.radians(alt)), np.nan)

    image = ax.imshow(
        airmass, aspect="auto", origin="lower", cmap="viridis_r",
        extent=[minutes[0] / 60, minutes[-1] / 60, 0, len(nights)],
    )
    ax.figure.colorbar(image, ax=ax, label="airmass")
    ax.set_xlabel("hours from local midnight")
    ax.set_ylabel(f"nights since {result.season_start.isoformat()}")
    return ax


def plot_altitude_sensitivity(
    result: ScheduleResult,
    *,
    ax=None,
    target_coord=None,
    observer_location=None,
    thresholds=None,
    marker_at=30.0,
):
    """
    Number of visible nights in the season as a function of the altitude cut,
    to see what a given threshold costs.
    """
    if target_coord is None or observer_location is None:
        raise ValueError(
            "target_coord and observer_location are required for plot_altitude_sensitivity"
        )
    from .visibility import visibility_allowed_offsets

    ax = _new_ax(ax, (6, 3.0))
    thresholds = list(thresholds) if thresholds is not None else list(range(0, 61, 5))
    counts = [
        len(
            visibility_allowed_offsets(
                result.season_start, result.season_end, target_coord, observer_location,
                min_altitude_deg=float(thr),
            )
        )
        for thr in thresholds
    ]
    ax.plot(thresholds, counts, marker="o", color=_NEW_COLOR)
    if marker_at is not None:
        ax.axvline(marker_at, color="#d62828", ls="--", lw=1, label=f"{marker_at:g}°")
        ax.legend(fontsize=8)
    ax.set_xlabel("min_altitude_deg")
    ax.set_ylabel("visible nights / season")
    return ax


def plot_summary(result: ScheduleResult, *, axes=None, allowed_offsets=None, windows=None):
    """
    Four-panel overview: timeline, night availability, phase coverage, and
    largest phase gap versus number of epochs. Returns the four Axes.

    If `result` was built with window, moon, or visibility constraints, pass
    the same pool as `allowed_offsets` -- without it, the night-availability
    and coverage-vs-N panels assume the whole season is observable and may
    not match a constrained result.
    """
    figure = None
    if axes is None:
        figure, axes = plt.subplots(2, 2, figsize=(12, 7))
    axes = np.asarray(axes).reshape(-1)
    plot_timeline(result, ax=axes[0], windows=windows)
    plot_night_availability(result, ax=axes[1], allowed_offsets=allowed_offsets)
    plot_phase_coverage(result, ax=axes[2])
    plot_coverage_vs_n(result, ax=axes[3], allowed_offsets=allowed_offsets)
    if figure is not None:
        figure.tight_layout(pad=2.5)
    return axes
