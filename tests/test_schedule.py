import math

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
