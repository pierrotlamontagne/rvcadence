from datetime import date

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

from rvcadence import plan_calendar
from rvcadence.plotting import (
    plot_constraint_breakdown,
    plot_greedy_vs_random,
    plot_night_availability,
    plot_phase_coverage,
    plot_timeline,
)

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


def test_plot_night_availability_marks_locked_and_new(result_with_locked):
    from rvcadence.plotting import plot_night_availability

    ax = plot_night_availability(result_with_locked, allowed_offsets=list(range(91)))
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert "already observed" in labels and "newly scheduled" in labels
    assert len(ax.images) == 1


def test_plot_night_availability_defaults_to_the_whole_season(result):
    from rvcadence.plotting import plot_night_availability

    ax = plot_night_availability(result)
    assert ax.images[0].get_array().shape[1] == (SEASON_END - SEASON_START).days + 1


def test_plot_constraint_breakdown_one_bar_per_entry(result):
    from rvcadence.plotting import plot_constraint_breakdown

    ax = plot_constraint_breakdown(result, counts={"season": 91, "moon": 78, "visibility": 60})
    assert len(ax.patches) == 3
    assert ax.get_ylabel() == "nights"


def test_plot_constraint_breakdown_requires_counts(result):
    from rvcadence.plotting import plot_constraint_breakdown

    with pytest.raises(ValueError, match="counts is required"):
        plot_constraint_breakdown(result)


def test_plot_greedy_vs_random_is_reproducible(result):
    from rvcadence.plotting import plot_greedy_vs_random

    a = plot_greedy_vs_random(result, seed=7)
    b = plot_greedy_vs_random(result, seed=7)
    # Read the bin counts off the BarContainer. ax.patches holds the filled
    # histogram's Rectangles *and* the stepped histogram's Polygon, which has
    # no get_height().
    assert list(a.containers[0].datavalues) == list(b.containers[0].datavalues)
    assert a.get_xlabel() == "orbital phase"
