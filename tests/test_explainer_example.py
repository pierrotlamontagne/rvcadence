import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("manim")

EXAMPLE_PATH = (
    Path(__file__).resolve().parents[1] / "examples" / "explainer" / "cadence_greedy_explainer.py"
)


def _load_example_module():
    spec = importlib.util.spec_from_file_location("cadence_greedy_explainer", EXAMPLE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_example_reuses_library_functions_by_identity():
    module = _load_example_module()
    from rvcadence import build_allowed_offsets, evaluate_candidate, parse_obs_windows

    assert module.evaluate_candidate is evaluate_candidate
    assert module.build_allowed_offsets is build_allowed_offsets
    assert module.parse_obs_windows is parse_obs_windows
