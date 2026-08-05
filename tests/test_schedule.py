import math

import pytest

try:
    import astropy.units as u
    from astropy.coordinates import EarthLocation, SkyCoord
except ImportError:
    pass  # individual tests below call pytest.importorskip("astropy") before using u/EarthLocation/SkyCoord

from rvcadence.schedule import (
    CandidateScore,
    best_candidate,
    build_schedule,
    evaluate_candidate,
    spacing_stats,
)


def test_evaluate_candidate_no_rotation():
    result = evaluate_candidate(t=5, selected=[0, 20], periods_d=10.0, p_rot_d=math.nan, baseline_days=20)
    assert isinstance(result, CandidateScore)
    assert result.t == 5
    assert result.d_p == 0.5
    assert result.d_r == 0.0
    assert result.d_t == 0.25
    assert result.score == 0.8 * 0.5 + 0.2 * 0.25


def test_evaluate_candidate_with_rotation():
    result = evaluate_candidate(t=5, selected=[0], periods_d=10.0, p_rot_d=4.0, baseline_days=20)
    assert result.d_r == min(abs((5 / 4.0) % 1.0 - (0 / 4.0) % 1.0), 1 - abs((5 / 4.0) % 1.0 - (0 / 4.0) % 1.0))
    assert result.score == 0.55 * result.d_p + 0.30 * result.d_r + 0.15 * result.d_t


def test_evaluate_candidate_single_float_matches_single_element_list():
    # Backward compatibility: a bare float is coerced to a single-element list.
    a = evaluate_candidate(t=5, selected=[0, 20], periods_d=10.0, p_rot_d=math.nan, baseline_days=20)
    b = evaluate_candidate(t=5, selected=[0, 20], periods_d=[10.0], p_rot_d=math.nan, baseline_days=20)
    assert a == b


def test_evaluate_candidate_multi_planet_uses_worst_case_min():
    # t=2 is well-phased for period 4.0 (d_p=0.5) but poorly phased for period
    # 100.0 (d_p=0.02) relative to selected=[0]. Worst-case aggregation must
    # surface the low value, not average it away with the high one.
    result = evaluate_candidate(
        t=2, selected=[0], periods_d=[4.0, 100.0], p_rot_d=math.nan, baseline_days=100,
    )
    assert result.d_p == min(0.5, 0.02)


def test_evaluate_candidate_empty_periods_raises():
    import pytest
    with pytest.raises(ValueError, match="periods_d must contain"):
        evaluate_candidate(t=5, selected=[0], periods_d=[], p_rot_d=math.nan, baseline_days=20)


def test_evaluate_candidate_nonpositive_period_raises():
    import pytest
    with pytest.raises(ValueError, match="periods_d must be positive"):
        evaluate_candidate(t=5, selected=[0], periods_d=-10.0, p_rot_d=math.nan, baseline_days=20)
    with pytest.raises(ValueError, match="periods_d must be positive"):
        evaluate_candidate(t=5, selected=[0], periods_d=[10.0, 0.0], p_rot_d=math.nan, baseline_days=20)


def test_evaluate_candidate_nonpositive_baseline_days_raises():
    import pytest
    with pytest.raises(ValueError, match="baseline_days must be positive"):
        evaluate_candidate(t=5, selected=[0], periods_d=10.0, p_rot_d=math.nan, baseline_days=0)


def test_best_candidate_ties_pick_earliest():
    # candidates 5 and 15 tie in score for period 10 seeded at [0, 20]; earliest wins
    candidates = list(range(0, 21))
    best = best_candidate(candidates, selected=[0, 20], periods_d=10.0, p_rot_d=math.nan, baseline_days=20)
    assert best.t == 5


def test_best_candidate_skips_selected_and_too_close():
    best = best_candidate([0, 1, 5, 20], selected=[0, 20], periods_d=10.0, p_rot_d=math.nan, baseline_days=20)
    assert best.t != 0 and best.t != 20


def test_build_schedule_toy_case():
    schedule = build_schedule(
        n_obs=3, periods_d=10.0, p_rot_d=math.nan,
        allowed_offsets=list(range(21)), baseline_days=20,
    )
    assert schedule == [0, 5, 20]


def test_build_schedule_multi_planet_analytic_pick():
    # Periods 4.0 and 5.0 share LCM=20 with the seeded baseline [0, 20], so
    # both periods sit at phase 0 for both seed points -- the third pick is
    # driven purely by worst-case (min) aggregation across the two periods.
    # Verified by hand: the unique max-score candidate is offset 2 (score
    # 0.34, tied with its mirror at offset 18; ties pick earliest per
    # test_best_candidate_ties_pick_earliest's existing behavior).
    schedule = build_schedule(
        n_obs=3, periods_d=[4.0, 5.0], p_rot_d=math.nan,
        allowed_offsets=list(range(21)), baseline_days=20,
    )
    assert schedule == [0, 2, 20]


def test_build_schedule_validates_periods_even_when_n_obs_is_one():
    # periods_d validation must fire before build_schedule's n_obs<=1
    # short-circuit, not only once the greedy scoring loop runs.
    import pytest
    with pytest.raises(ValueError, match="periods_d must contain"):
        build_schedule(1, [], math.nan, [3, 7, 12], baseline_days=12)


def test_build_schedule_single_observation():
    assert build_schedule(1, 10.0, math.nan, [3, 7, 12], baseline_days=12) == [3]


def test_build_schedule_zero_observations():
    assert build_schedule(0, 10.0, math.nan, [3, 7, 12], baseline_days=12) == []


def test_build_schedule_raises_on_too_few_candidates():
    import pytest
    with pytest.raises(ValueError, match="Only one feasible candidate"):
        build_schedule(2, 10.0, math.nan, [5], baseline_days=12)


def test_build_schedule_raises_on_no_candidates():
    import pytest
    with pytest.raises(ValueError, match="No candidate dates"):
        build_schedule(2, 10.0, math.nan, [], baseline_days=12)


def test_spacing_stats():
    # gaps are [5, 15]; median and mean of two values are both their average
    assert spacing_stats([0, 5, 20]) == (10.0, 10.0)


def test_spacing_stats_too_few_points():
    med, mean = spacing_stats([5])
    assert math.isnan(med) and math.isnan(mean)


# append to tests/test_schedule.py
from datetime import date

from rvcadence.schedule import ScheduleResult, plan_calendar


def test_plan_calendar_toy_case():
    result = plan_calendar(
        n_obs=3,
        periods_d=10.0,
        season_start=date(2026, 1, 1),
        season_end=date(2026, 1, 21),
    )
    assert isinstance(result, ScheduleResult)
    assert result.dates == [date(2026, 1, 1), date(2026, 1, 6), date(2026, 1, 21)]
    assert result.median_gap_d == 10.0
    assert result.mean_gap_d == 10.0


def test_plan_calendar_accepts_window_text():
    result = plan_calendar(
        n_obs=2,
        periods_d=10.0,
        season_start=date(2026, 1, 1),
        season_end=date(2026, 1, 21),
        windows="2026-01-05 to 2026-01-15",
    )
    assert all(date(2026, 1, 5) <= d <= date(2026, 1, 15) for d in result.dates)


def test_plan_calendar_accepts_multiple_periods():
    # Plumbing check: a single-element list must behave identically to the
    # bare-float form (the aggregation logic itself is unit-tested in
    # test_schedule.py's evaluate_candidate tests, Task 4).
    result_single = plan_calendar(
        n_obs=3, periods_d=10.0,
        season_start=date(2026, 1, 1), season_end=date(2026, 1, 21),
    )
    result_list = plan_calendar(
        n_obs=3, periods_d=[10.0],
        season_start=date(2026, 1, 1), season_end=date(2026, 1, 21),
    )
    assert result_single == result_list


# append to tests/test_schedule.py
def test_plan_calendar_with_moon_avoidance_drops_polluted_offset_zero():
    pytest.importorskip("astropy")
    import astropy.units as u
    from astropy.coordinates import EarthLocation
    from rvcadence.moon import moon_coord_at_midnight

    paranal = EarthLocation(lat=-24.6272 * u.deg, lon=-70.4039 * u.deg, height=2635 * u.m)
    season_start = date(2026, 6, 1)
    season_end = date(2026, 6, 21)
    moon_coord = moon_coord_at_midnight(season_start, paranal)

    result = plan_calendar(
        n_obs=3,
        periods_d=10.0,
        season_start=season_start,
        season_end=season_end,
        target_coord=moon_coord,
        observer_location=paranal,
        min_moon_sep_deg=30.0,
    )
    assert season_start not in result.dates


def test_plan_calendar_target_coord_without_observer_location_raises():
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    with pytest.raises(ValueError, match="observer_location is required"):
        plan_calendar(
            n_obs=2, periods_d=10.0,
            season_start=date(2026, 1, 1), season_end=date(2026, 1, 21),
            target_coord=SkyCoord(ra=10 * u.deg, dec=10 * u.deg),
        )


def test_plan_calendar_observer_location_without_target_coord_raises():
    pytest.importorskip("astropy")
    import astropy.units as u
    from astropy.coordinates import EarthLocation
    paranal = EarthLocation(lat=-24.6272 * u.deg, lon=-70.4039 * u.deg, height=2635 * u.m)
    with pytest.raises(ValueError, match="target_coord is required"):
        plan_calendar(
            n_obs=2, periods_d=10.0,
            season_start=date(2026, 1, 1), season_end=date(2026, 1, 21),
            observer_location=paranal,
        )


def test_plan_calendar_resolves_string_target_and_site(capsys):
    pytest.importorskip("astropy")
    try:
        result = plan_calendar(
            n_obs=2,
            periods_d=10.0,
            season_start=date(2026, 1, 15),
            season_end=date(2026, 1, 25),
            target_coord="Sirius",
            observer_location="Paranal Observatory",
            min_altitude_deg=30.0,
            min_moon_sep_deg=None,
        )
    except Exception as exc:
        pytest.skip(f"Name resolution unavailable: {exc}")
    assert len(result.dates) == 2
    captured = capsys.readouterr()
    assert "Sirius" in captured.out and "Paranal Observatory" in captured.out


def test_plan_calendar_min_altitude_deg_excludes_never_visible_target():
    pytest.importorskip("astropy")
    paranal = EarthLocation(lat=-24.6272 * u.deg, lon=-70.4039 * u.deg, height=2635 * u.m)
    polaris = SkyCoord(ra=37.95456067 * u.deg, dec=89.26410897 * u.deg)
    with pytest.raises(ValueError, match="No candidate dates"):
        plan_calendar(
            n_obs=2,
            periods_d=10.0,
            season_start=date(2026, 1, 15),
            season_end=date(2026, 1, 25),
            target_coord=polaris,
            observer_location=paranal,
            min_altitude_deg=0.0,
            min_moon_sep_deg=None,
        )


def test_plan_calendar_windows_and_visibility_intersect():
    pytest.importorskip("astropy")
    paranal = EarthLocation(lat=-24.6272 * u.deg, lon=-70.4039 * u.deg, height=2635 * u.m)
    sirius = SkyCoord(ra=101.28715533 * u.deg, dec=-16.71611586 * u.deg)  # always visible in this range
    result = plan_calendar(
        n_obs=2,
        periods_d=10.0,
        season_start=date(2026, 1, 1),
        season_end=date(2026, 1, 31),
        windows="2026-01-15 to 2026-01-25",
        target_coord=sirius,
        observer_location=paranal,
        min_altitude_deg=30.0,
        min_moon_sep_deg=None,
    )
    assert all(date(2026, 1, 15) <= d <= date(2026, 1, 25) for d in result.dates)


def test_plan_calendar_min_moon_sep_deg_none_skips_moon_check():
    # Moon-coincident target would normally be excluded by the default
    # min_moon_sep_deg=30.0; passing None must let it through instead.
    pytest.importorskip("astropy")
    from rvcadence.moon import moon_coord_at_midnight

    paranal = EarthLocation(lat=-24.6272 * u.deg, lon=-70.4039 * u.deg, height=2635 * u.m)
    season_start = date(2026, 6, 1)
    moon_coord = moon_coord_at_midnight(season_start, paranal)

    result = plan_calendar(
        n_obs=2,
        periods_d=10.0,
        season_start=season_start,
        season_end=date(2026, 6, 21),
        target_coord=moon_coord,
        observer_location=paranal,
        min_moon_sep_deg=None,
    )
    assert season_start in result.dates


def test_evaluate_candidate_custom_weights_no_rotation():
    result = evaluate_candidate(
        t=5, selected=[0, 20], periods_d=10.0, p_rot_d=math.nan,
        baseline_days=20, weights=(0.5, 0.5),
    )
    assert result.score == 0.5 * result.d_p + 0.5 * result.d_t


def test_evaluate_candidate_custom_weights_with_rotation():
    result = evaluate_candidate(
        t=5, selected=[0], periods_d=10.0, p_rot_d=4.0,
        baseline_days=20, weights=(0.6, 0.3, 0.1),
    )
    assert result.score == 0.6 * result.d_p + 0.3 * result.d_r + 0.1 * result.d_t


def test_evaluate_candidate_weights_none_reproduces_defaults():
    a = evaluate_candidate(t=5, selected=[0], periods_d=10.0, p_rot_d=4.0, baseline_days=20)
    b = evaluate_candidate(
        t=5, selected=[0], periods_d=10.0, p_rot_d=4.0,
        baseline_days=20, weights=(0.55, 0.30, 0.15),
    )
    assert a.score == b.score


def test_evaluate_candidate_weights_wrong_length_with_rotation_raises():
    with pytest.raises(ValueError, match="weights must have 3 entries"):
        evaluate_candidate(
            t=5, selected=[0], periods_d=10.0, p_rot_d=4.0,
            baseline_days=20, weights=(0.8, 0.2),
        )


def test_evaluate_candidate_weights_wrong_length_without_rotation_raises():
    with pytest.raises(ValueError, match="weights must have 2 entries"):
        evaluate_candidate(
            t=5, selected=[0], periods_d=10.0, p_rot_d=math.nan,
            baseline_days=20, weights=(0.55, 0.30, 0.15),
        )


def test_evaluate_candidate_weights_negative_raises():
    with pytest.raises(ValueError, match="weights must be non-negative"):
        evaluate_candidate(
            t=5, selected=[0], periods_d=10.0, p_rot_d=math.nan,
            baseline_days=20, weights=(1.2, -0.2),
        )


def test_evaluate_candidate_weights_do_not_sum_to_one_raises():
    with pytest.raises(ValueError, match="weights must sum to 1"):
        evaluate_candidate(
            t=5, selected=[0], periods_d=10.0, p_rot_d=math.nan,
            baseline_days=20, weights=(0.7, 0.2),
        )


def test_evaluate_candidate_nan_weight_raises():
    # Every comparison against NaN is False, so a NaN slips past both the sign
    # and the sum check unless it is rejected on its own.
    with pytest.raises(ValueError, match="weights must be finite"):
        evaluate_candidate(
            t=5, selected=[0], periods_d=10.0, p_rot_d=math.nan,
            baseline_days=20, weights=(math.nan, 0.2),
        )


def test_plan_calendar_weights_change_the_schedule():
    kwargs = dict(
        n_obs=4, periods_d=10.0,
        season_start=date(2026, 1, 1), season_end=date(2026, 1, 21),
        rotation_period_d=3.0,
    )
    default = plan_calendar(**kwargs)
    time_only = plan_calendar(**kwargs, weights=(0.0, 0.0, 1.0))
    # default picks 2026-01-05 and 2026-01-08; pure temporal spread picks
    # 2026-01-06 and 2026-01-11.
    assert default.dates != time_only.dates


def test_planet_weights_none_keeps_worst_case_min():
    # Same fixture as test_evaluate_candidate_multi_planet_uses_worst_case_min.
    result = evaluate_candidate(
        t=2, selected=[0], periods_d=[4.0, 100.0], p_rot_d=math.nan, baseline_days=100,
    )
    assert result.d_p == min(0.5, 0.02)


def test_planet_weights_uses_weighted_mean():
    result = evaluate_candidate(
        t=2, selected=[0], periods_d=[4.0, 100.0], p_rot_d=math.nan,
        baseline_days=100, planet_weights=[0.25, 0.75],
    )
    assert result.d_p == pytest.approx(0.25 * 0.5 + 0.75 * 0.02)


def test_planet_weights_stay_within_zero_and_half():
    result = evaluate_candidate(
        t=2, selected=[0], periods_d=[4.0, 100.0], p_rot_d=math.nan,
        baseline_days=100, planet_weights=[0.5, 0.5],
    )
    assert 0.0 <= result.d_p <= 0.5


def test_planet_weights_wrong_length_raises():
    with pytest.raises(ValueError, match="planet_weights must have one entry per period"):
        evaluate_candidate(
            t=2, selected=[0], periods_d=[4.0, 100.0], p_rot_d=math.nan,
            baseline_days=100, planet_weights=[1.0],
        )


def test_planet_weights_negative_raises():
    with pytest.raises(ValueError, match="planet_weights must be non-negative"):
        evaluate_candidate(
            t=2, selected=[0], periods_d=[4.0, 100.0], p_rot_d=math.nan,
            baseline_days=100, planet_weights=[1.2, -0.2],
        )


def test_planet_weights_do_not_sum_to_one_raises():
    with pytest.raises(ValueError, match="planet_weights must sum to 1"):
        evaluate_candidate(
            t=2, selected=[0], periods_d=[4.0, 100.0], p_rot_d=math.nan,
            baseline_days=100, planet_weights=[0.5, 0.2],
        )


def test_planet_weights_nan_raises():
    with pytest.raises(ValueError, match="planet_weights must be finite"):
        evaluate_candidate(
            t=2, selected=[0], periods_d=[4.0, 100.0], p_rot_d=math.nan,
            baseline_days=100, planet_weights=[math.nan, 0.5],
        )


def test_planet_weights_do_not_affect_rotation_term():
    kwargs = dict(
        t=7, selected=[0, 3], periods_d=[4.0, 11.0], p_rot_d=9.0, baseline_days=40,
    )
    a = evaluate_candidate(**kwargs)
    b = evaluate_candidate(**kwargs, planet_weights=[0.9, 0.1])
    assert a.d_r == b.d_r


def _largest_phase_gap(dates, ref, period_d):
    phases = sorted(((d - ref).days % period_d) / period_d for d in dates)
    gaps = [b - a for a, b in zip(phases, phases[1:])]
    gaps.append(1.0 - phases[-1] + phases[0])
    return max(gaps)


def test_planet_weights_prioritise_the_favoured_planet():
    ref = date(2026, 1, 1)
    kwargs = dict(
        n_obs=12, periods_d=[7.3, 23.1],
        season_start=ref, season_end=date(2026, 7, 1),
    )
    first = plan_calendar(**kwargs, planet_weights=[0.9, 0.1])
    second = plan_calendar(**kwargs, planet_weights=[0.1, 0.9])

    assert _largest_phase_gap(first.dates, ref, 7.3) < _largest_phase_gap(second.dates, ref, 7.3)
    assert _largest_phase_gap(second.dates, ref, 23.1) < _largest_phase_gap(first.dates, ref, 23.1)


def test_plan_calendar_planet_weights_none_matches_v0_2_output():
    # The 0.2.0 multi-planet schedule, pinned so the opt-in default cannot drift.
    result = plan_calendar(
        n_obs=3, periods_d=[4.0, 5.0],
        season_start=date(2026, 1, 1), season_end=date(2026, 1, 21),
    )
    assert result.dates == [date(2026, 1, 1), date(2026, 1, 3), date(2026, 1, 21)]


def test_d_t_is_clipped_at_one_for_distant_epochs():
    result = evaluate_candidate(
        t=5, selected=[-400], periods_d=10.0, p_rot_d=math.nan, baseline_days=20,
    )
    assert result.d_t == 1.0


def test_d_t_clip_does_not_change_in_range_values():
    result = evaluate_candidate(
        t=5, selected=[0, 20], periods_d=10.0, p_rot_d=math.nan, baseline_days=20,
    )
    assert result.d_t == 0.25


def test_build_schedule_locks_existing_offsets():
    schedule = build_schedule(
        n_obs=5, periods_d=10.0, p_rot_d=math.nan,
        allowed_offsets=list(range(41)), baseline_days=40,
        existing_offsets=[3, 17],
    )
    assert 3 in schedule and 17 in schedule
    assert len(schedule) == 5
    assert schedule == sorted(schedule)


def test_build_schedule_never_reselects_a_locked_offset():
    schedule = build_schedule(
        n_obs=6, periods_d=10.0, p_rot_d=math.nan,
        allowed_offsets=list(range(41)), baseline_days=40,
        existing_offsets=[3, 17],
    )
    assert len(set(schedule)) == len(schedule)


def test_build_schedule_locks_offsets_outside_the_allowed_pool():
    schedule = build_schedule(
        n_obs=4, periods_d=10.0, p_rot_d=math.nan,
        allowed_offsets=list(range(20, 41)), baseline_days=40,
        existing_offsets=[-5, 2],
    )
    assert -5 in schedule and 2 in schedule
    assert len(schedule) == 4


def test_best_candidate_min_gap_screens_candidates_near_a_locked_offset():
    # build_schedule always uses min_gap_days=1, which cannot bind: candidates
    # are distinct integers not already selected, so `abs(t - s) < 1` is never
    # true. Exercise the screen through best_candidate's own min_gap_days, on a
    # fixture where it changes the answer: with a locked epoch at 5 the best
    # candidate is 3, but a 3-day gap rules out 3, 4, 6 and 7 and the winner
    # becomes 2.
    pool = [1, 2, 3, 4, 6, 7, 8, 9]
    kwargs = dict(
        selected=[5], periods_d=4.0, p_rot_d=math.nan, baseline_days=10,
    )
    assert best_candidate(pool, min_gap_days=1, **kwargs).t == 3
    assert best_candidate(pool, min_gap_days=3, **kwargs).t == 2


def test_best_candidate_raises_when_min_gap_leaves_nothing():
    with pytest.raises(RuntimeError, match="Could not find feasible"):
        best_candidate(
            [3, 4, 5, 6, 7], selected=[5], periods_d=10.0, p_rot_d=math.nan,
            baseline_days=10, min_gap_days=3,
        )


def test_build_schedule_new_offsets_are_distinct_from_locked():
    schedule = build_schedule(
        n_obs=4, periods_d=10.0, p_rot_d=math.nan,
        allowed_offsets=list(range(41)), baseline_days=40,
        existing_offsets=[10, 11],
    )
    assert schedule.count(10) == 1 and schedule.count(11) == 1
    assert len(set(schedule)) == len(schedule)


def test_build_schedule_returns_only_locked_when_budget_is_exhausted():
    schedule = build_schedule(
        n_obs=2, periods_d=10.0, p_rot_d=math.nan,
        allowed_offsets=list(range(41)), baseline_days=40,
        existing_offsets=[3, 17, 29],
    )
    assert schedule == [3, 17, 29]


def test_build_schedule_existing_offsets_none_matches_v0_2():
    assert build_schedule(
        n_obs=3, periods_d=10.0, p_rot_d=math.nan,
        allowed_offsets=list(range(21)), baseline_days=20,
        existing_offsets=None,
    ) == [0, 5, 20]


def test_single_remaining_epoch_is_not_pinned_to_season_end():
    # One locked epoch at offset 0 and one slot left. Offsets 5 and 15 both sit
    # at phase 0.5 for a 10 d period, so the spread term decides between them
    # and picks 15 -- the last night of the season, offset 20, is at phase 0
    # and is not chosen.
    schedule = build_schedule(
        n_obs=2, periods_d=10.0, p_rot_d=math.nan,
        allowed_offsets=list(range(21)), baseline_days=20,
        existing_offsets=[0],
    )
    assert schedule == [0, 15]


def test_plan_calendar_existing_times_splits_locked_and_new():
    result = plan_calendar(
        n_obs=5, periods_d=10.0,
        season_start=date(2026, 1, 1), season_end=date(2026, 2, 10),
        existing_times=[date(2026, 1, 4), date(2026, 1, 18)],
    )
    assert result.locked_dates == [date(2026, 1, 4), date(2026, 1, 18)]
    assert len(result.new_dates) == 3
    assert result.n_remaining == 3
    assert result.dates == sorted(result.locked_dates + result.new_dates)
    assert not set(result.locked_dates) & set(result.new_dates)


def test_plan_calendar_existing_times_from_mjd_floats():
    # MJD 61041.0 is 2026-01-01, 61051.0 is 2026-01-11.
    result = plan_calendar(
        n_obs=4, periods_d=10.0,
        season_start=date(2026, 1, 1), season_end=date(2026, 2, 10),
        existing_times=[61041.0, 61051.0],
    )
    assert result.locked_dates == [date(2026, 1, 1), date(2026, 1, 11)]


def test_plan_calendar_existing_times_none_matches_v0_2():
    result = plan_calendar(
        n_obs=3, periods_d=10.0,
        season_start=date(2026, 1, 1), season_end=date(2026, 1, 21),
    )
    assert result.dates == [date(2026, 1, 1), date(2026, 1, 6), date(2026, 1, 21)]
    assert result.locked_dates == []
    assert result.new_dates == result.dates
    assert result.n_remaining == 3
    assert result.median_gap_d == 10.0
    assert result.mean_gap_d == 10.0


def test_plan_calendar_budget_exhausted_returns_locked_only_and_warns():
    # More observed than requested: the extra epochs are kept, not discarded,
    # but len(dates) > n_obs is surprising enough to warn about.
    with pytest.warns(UserWarning, match="already observed"):
        result = plan_calendar(
            n_obs=2, periods_d=10.0,
            season_start=date(2026, 1, 1), season_end=date(2026, 2, 10),
            existing_times=[date(2026, 1, 4), date(2026, 1, 18), date(2026, 1, 25)],
        )
    assert result.new_dates == []
    assert result.n_remaining == 0
    assert len(result.locked_dates) == 3


def test_plan_calendar_does_not_warn_when_within_budget(recwarn):
    plan_calendar(
        n_obs=5, periods_d=10.0,
        season_start=date(2026, 1, 1), season_end=date(2026, 2, 10),
        existing_times=[date(2026, 1, 4), date(2026, 1, 18)],
    )
    assert not [w for w in recwarn if "already observed" in str(w.message)]


def test_plan_calendar_locked_epochs_before_the_season_are_kept():
    result = plan_calendar(
        n_obs=4, periods_d=10.0,
        season_start=date(2026, 1, 1), season_end=date(2026, 2, 10),
        existing_times=[date(2025, 6, 1)],
    )
    assert result.locked_dates == [date(2025, 6, 1)]
    assert len(result.new_dates) == 3
    assert all(d >= date(2026, 1, 1) for d in result.new_dates)


def test_plan_calendar_gap_stats_ignore_epochs_outside_the_season():
    # A locked epoch outside the season is still excluded from the
    # median/mean gap: they are recomputed here from the returned
    # in-season offsets directly, rather than compared across two
    # independent plan_calendar() calls, because a locked epoch also
    # changes which in-season dates the greedy loop goes on to pick.
    season_start = date(2026, 1, 1)
    result = plan_calendar(
        n_obs=4, periods_d=10.0,
        season_start=season_start, season_end=date(2026, 2, 10),
        existing_times=[date(2025, 6, 1)],
    )
    in_season_offsets = sorted((d - season_start).days for d in result.new_dates)
    expected_median, expected_mean = spacing_stats(in_season_offsets)
    assert result.median_gap_d == expected_median
    assert result.mean_gap_d == expected_mean


def test_plan_calendar_duplicate_nights_collapse():
    result = plan_calendar(
        n_obs=4, periods_d=10.0,
        season_start=date(2026, 1, 1), season_end=date(2026, 2, 10),
        existing_times=[date(2026, 1, 4), date(2026, 1, 4)],
    )
    assert result.locked_dates == [date(2026, 1, 4)]
    assert len(result.new_dates) == 3


def test_plan_calendar_rjd_existing_times():
    # RJD 61041.5 is 2026-01-01T00:00:00 UTC.
    result = plan_calendar(
        n_obs=3, periods_d=10.0,
        season_start=date(2026, 1, 1), season_end=date(2026, 2, 10),
        existing_times=[61041.5], time_format="rjd",
    )
    assert result.locked_dates == [date(2026, 1, 1)]
