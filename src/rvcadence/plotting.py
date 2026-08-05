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
