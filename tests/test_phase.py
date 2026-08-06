import pytest

from rvcadence._phase import circ_dist_01, max_phase_gap, min_phase_separation, min_time_separation


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


def test_max_phase_gap_evenly_spaced():
    # Offsets 0, 2, 4, 6, 8 fold onto phases 0, 0.2, 0.4, 0.6, 0.8 for P = 10.
    assert max_phase_gap([0, 2, 4, 6, 8], 10.0) == pytest.approx(0.2)


def test_max_phase_gap_wraps_across_the_boundary():
    # Phases 0.1 and 0.3 leave a 0.8 gap through the wrap.
    assert max_phase_gap([1, 3], 10.0) == pytest.approx(0.8)


def test_max_phase_gap_single_epoch_is_the_whole_circle():
    assert max_phase_gap([4], 10.0) == pytest.approx(1.0)


def test_max_phase_gap_empty():
    assert max_phase_gap([], 10.0) == 1.0
