import pytest

pytest.importorskip("astropy")

from rvcadence.target import resolve_site_name, resolve_target_name


def test_resolve_target_name_known_object(capsys):
    try:
        coord = resolve_target_name("Vega")
    except Exception as exc:
        pytest.skip(f"Sesame name resolution unavailable: {exc}")
    assert abs(coord.ra.deg - 279.2347) < 0.1
    assert abs(coord.dec.deg - 38.7837) < 0.1
    captured = capsys.readouterr()
    assert "Vega" in captured.out


def test_resolve_site_name_known_site(capsys):
    try:
        location = resolve_site_name("Paranal Observatory")
    except Exception as exc:
        pytest.skip(f"Site registry unavailable: {exc}")
    assert abs(location.lat.deg - (-24.6274)) < 0.01
    assert abs(location.lon.deg - (-70.4050)) < 0.01
    captured = capsys.readouterr()
    assert "Paranal Observatory" in captured.out
