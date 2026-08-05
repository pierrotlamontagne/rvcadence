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


def test_plot_night_availability_ignores_pre_season_locked_epochs():
    from rvcadence.plotting import plot_night_availability

    pre_season = plan_calendar(
        n_obs=8, periods_d=[9.53, 21.7],
        season_start=SEASON_START, season_end=SEASON_END,
        rotation_period_d=12.45,
        existing_times=[date(2025, 11, 1), date(2026, 1, 20)],
    )
    ax = plot_night_availability(pre_season)
    xmin, _ = ax.get_xlim()
    assert xmin >= 0
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert "already observed" in labels


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
    c = plot_greedy_vs_random(result, seed=8)
    # The greedy histogram is seed-independent, so containers[0].datavalues
    # cannot exercise the RNG. ax.patches[-1] is the stepped random
    # histogram's Polygon -- the vertices that actually move with the seed.
    assert a.patches[-1].get_xy().tolist() == b.patches[-1].get_xy().tolist()
    assert a.patches[-1].get_xy().tolist() != c.patches[-1].get_xy().tolist()
    assert a.get_xlabel() == "orbital phase"


def test_plot_phase_vs_rotation_phase_axes_are_phases(result):
    from rvcadence.plotting import plot_phase_vs_rotation_phase

    ax = plot_phase_vs_rotation_phase(result)
    assert ax.get_xlim() == (0.0, 1.0)
    assert ax.get_ylim() == (0.0, 1.0)
    assert "rotation phase" in ax.get_ylabel()


def test_plot_phase_vs_rotation_phase_requires_a_rotation_period():
    from rvcadence.plotting import plot_phase_vs_rotation_phase

    no_rotation = plan_calendar(
        n_obs=5, periods_d=9.53, season_start=SEASON_START, season_end=SEASON_END,
    )
    with pytest.raises(ValueError, match="needs a rotation period"):
        plot_phase_vs_rotation_phase(no_rotation)


def test_plot_coverage_vs_n_one_line_per_planet(result):
    from rvcadence.plotting import plot_coverage_vs_n

    ax = plot_coverage_vs_n(result)
    assert len(ax.lines) == len(result.periods_d)
    assert ax.get_ylabel() == "largest phase gap"


def test_coverage_vs_n_is_monotonically_non_increasing(result):
    from rvcadence.plotting import plot_coverage_vs_n

    ax = plot_coverage_vs_n(result, n_values=range(2, 13))
    for line in ax.lines:
        gaps = list(line.get_ydata())
        assert all(b <= a + 1e-12 for a, b in zip(gaps, gaps[1:])), gaps


def test_coverage_vs_n_ends_at_the_actual_schedule(result):
    # The last point on the curve must be the largest phase gap of the schedule
    # the result actually holds -- the curve re-runs the same optimization.
    from rvcadence._phase import max_phase_gap
    from rvcadence.plotting import plot_coverage_vs_n

    ax = plot_coverage_vs_n(result)
    offsets = [(d - result.season_start).days for d in result.dates]
    for line, period in zip(ax.lines, result.periods_d):
        assert line.get_ydata()[-1] == pytest.approx(max_phase_gap(offsets, period))


def test_coverage_vs_n_honours_custom_weights():
    # Built with planet_weights heavily favouring the second planet: the curve
    # must reflect that optimization, not the default worst-case one.
    from rvcadence._phase import max_phase_gap
    from rvcadence.plotting import plot_coverage_vs_n

    tuned = plan_calendar(
        n_obs=10, periods_d=[9.53, 21.7],
        season_start=SEASON_START, season_end=SEASON_END,
        planet_weights=[0.05, 0.95],
    )
    ax = plot_coverage_vs_n(tuned)
    offsets = [(d - tuned.season_start).days for d in tuned.dates]
    for line, period in zip(ax.lines, tuned.periods_d):
        assert line.get_ydata()[-1] == pytest.approx(max_phase_gap(offsets, period))


def test_coverage_vs_n_honours_locked_epochs():
    from rvcadence._phase import max_phase_gap
    from rvcadence.plotting import plot_coverage_vs_n

    mid = plan_calendar(
        n_obs=10, periods_d=[9.53, 21.7],
        season_start=SEASON_START, season_end=SEASON_END,
        existing_times=[date(2026, 1, 3), date(2026, 1, 20), date(2026, 2, 8)],
    )
    ax = plot_coverage_vs_n(mid)
    offsets = [(d - mid.season_start).days for d in mid.dates]
    for line, period in zip(ax.lines, mid.periods_d):
        assert line.get_ydata()[-1] == pytest.approx(max_phase_gap(offsets, period))


def _paranal_and_sirius():
    pytest.importorskip("astropy")
    import astropy.units as u
    from astropy.coordinates import EarthLocation, SkyCoord

    site = EarthLocation(lat=-24.6272 * u.deg, lon=-70.4039 * u.deg, height=2635 * u.m)
    target = SkyCoord(ra=101.28715533 * u.deg, dec=-16.71611586 * u.deg)
    return site, target


def test_plot_staralt_returns_a_heatmap():
    from rvcadence.plotting import plot_staralt

    site, target = _paranal_and_sirius()
    short = plan_calendar(
        n_obs=3, periods_d=9.53,
        season_start=date(2026, 1, 1), season_end=date(2026, 1, 15),
    )
    ax = plot_staralt(short, target_coord=target, observer_location=site)
    assert len(ax.images) == 1
    assert ax.images[0].get_array().shape[0] == 15


def test_plot_staralt_requires_a_target_and_site(result):
    from rvcadence.plotting import plot_staralt

    pytest.importorskip("astropy")
    with pytest.raises(ValueError, match="target_coord and observer_location are required"):
        plot_staralt(result)


def test_plot_altitude_sensitivity_is_non_increasing():
    from rvcadence.plotting import plot_altitude_sensitivity

    site, target = _paranal_and_sirius()
    short = plan_calendar(
        n_obs=3, periods_d=9.53,
        season_start=date(2026, 1, 1), season_end=date(2026, 1, 15),
    )
    # This target transits at ~82deg from this site, so thresholds below that
    # exclude nothing; 85 sits past culmination and drops the count to 0,
    # giving the monotonicity check a threshold it can actually fail on.
    ax = plot_altitude_sensitivity(
        short, target_coord=target, observer_location=site, thresholds=[0, 60, 85],
    )
    counts = list(ax.lines[0].get_ydata())
    assert all(b <= a for a, b in zip(counts, counts[1:]))
    # A pure non-increasing check passes trivially on a constant sequence, so
    # on its own it can't tell "the cut has no effect" from "the cut works" --
    # require an actual drop across the range to make that distinguishable.
    assert counts[-1] < counts[0]
    assert ax.get_xlabel() == "min_altitude_deg"


def test_plot_summary_returns_four_axes(result):
    import matplotlib.pyplot as plt
    from rvcadence.plotting import plot_summary

    axes = plot_summary(result)
    assert len(axes) == 4
    assert all(isinstance(a, matplotlib.axes.Axes) for a in axes)
    plt.close(axes[0].figure)


def test_plot_summary_draws_into_supplied_axes(result):
    import matplotlib.pyplot as plt
    from rvcadence.plotting import plot_summary

    fig, given = plt.subplots(2, 2)
    axes = plot_summary(result, axes=given)
    assert {a.figure for a in axes} == {fig}
    plt.close(fig)


def test_plot_summary_marks_locked_epochs(result_with_locked):
    import matplotlib.pyplot as plt
    from rvcadence.plotting import plot_summary

    axes = plot_summary(result_with_locked)
    labels = [t.get_text() for a in axes if a.get_legend() for t in a.get_legend().get_texts()]
    assert "already observed" in labels
    plt.close(axes[0].figure)
