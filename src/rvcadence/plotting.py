"""
Matplotlib figures for a ScheduleResult.

Requires `pip install rvcadence[plot]`. Not re-exported at package level;
import from here directly. Every function takes the result as its first
argument, draws into `ax` when given and creates its own figure otherwise,
and returns the Axes, so the figures compose.
"""

from __future__ import annotations

import math
from datetime import timedelta

import numpy as np

try:
    import matplotlib.pyplot as plt
except ImportError as exc:  # pragma: no cover - exercised only without matplotlib
    raise ImportError(
        "rvcadence.plotting requires matplotlib. Install it with: pip install rvcadence[plot]"
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
    ax.set_xlabel("date")
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
        idx = _offsets(dates, result.season_start)
        ax.scatter(
            idx, [0.5] * len(idx), marker=marker, s=140, color=color,
            edgecolor="white", linewidth=0.6, zorder=3, label=label,
        )
    ax.set_yticks([])
    ax.set_xlabel(f"days since {result.season_start.isoformat()}")
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
