from datetime import date

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

from rvcadence import plan_calendar
from rvcadence.plotting import plot_phase_coverage, plot_timeline

SEASON_START = date(2026, 1, 1)
SEASON_END = date(2026, 4, 1)


@pytest.fixture
def result():
    return plan_calendar(
        n_obs=8, periods_d=[9.53, 21.7],
        season_start=SEASON_START, season_end=SEASON_END,
        rotation_period_d=12.45,
    )


@pytest.fixture
def result_with_locked():
    return plan_calendar(
        n_obs=8, periods_d=[9.53, 21.7],
        season_start=SEASON_START, season_end=SEASON_END,
        rotation_period_d=12.45,
        existing_times=[date(2026, 1, 3), date(2026, 1, 20)],
    )


def test_plot_timeline_returns_axes(result):
    ax = plot_timeline(result)
    assert isinstance(ax, matplotlib.axes.Axes)


def test_plot_timeline_draws_into_a_supplied_axes(result):
    import matplotlib.pyplot as plt

    _, ax = plt.subplots()
    assert plot_timeline(result, ax=ax) is ax


def test_plot_timeline_separates_locked_and_new(result_with_locked):
    ax = plot_timeline(result_with_locked)
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert "already observed" in labels
    assert "newly scheduled" in labels


def test_plot_timeline_without_locked_epochs_has_no_locked_entry(result):
    ax = plot_timeline(result)
    legend = ax.get_legend()
    labels = [] if legend is None else [t.get_text() for t in legend.get_texts()]
    assert "already observed" not in labels


def test_plot_phase_coverage_one_row_per_period(result):
    ax = plot_phase_coverage(result)
    assert len(ax.get_yticks()) == len(result.periods_d)
    assert ax.get_xlabel() == "orbital phase"


def test_plot_phase_coverage_locked_and_new_are_separate_artists(result_with_locked):
    ax = plot_phase_coverage(result_with_locked)
    # get_facecolor()[0][:3] is a numpy array, which is unhashable -- convert
    # to a tuple before putting it in a set.
    colors = {tuple(c.get_facecolor()[0][:3]) for c in ax.collections}
    assert len(colors) == 2
