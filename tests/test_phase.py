import pytest

from rvcadence._phase import circ_dist_01, min_phase_separation, min_time_separation


def test_circ_dist_01_wraps_around():
    assert circ_dist_01(0.05, 0.95) == pytest.approx(0.1)


def test_circ_dist_01_same_point_is_zero():
    assert circ_dist_01(0.3, 0.3) == 0.0


def test_min_phase_separation_empty_list_returns_half():
    assert min_phase_separation(0.2, []) == 0.5


def test_min_phase_separation_picks_closest():
    assert min_phase_separation(0.5, [0.1, 0.45, 0.9]) == pytest.approx(0.05)


def test_min_time_separation_empty_list_returns_inf():
    assert min_time_separation(10, []) == float("inf")


def test_min_time_separation_picks_closest():
    assert min_time_separation(10, [2, 8, 20]) == 2.0
