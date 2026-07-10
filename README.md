# rvcadence

Greedy observing-calendar scheduler for radial-velocity follow-up campaigns.

Given a number of observations to schedule, one or more planets' orbital
periods (and, optionally, the star's rotation period), and a set of
visibility windows, `rvcadence` picks the calendar dates that best cover all
phase cycles while keeping observations temporally spread out. Optionally
excludes nights where the Moon is too close to the target for
high-resolution spectroscopy.

![Algorithm walkthrough](docs/cadence_greedy_explainer.gif)

Full-quality version: [`examples/explainer/CadenceGreedyExplainer.mp4`](examples/explainer/CadenceGreedyExplainer.mp4)

## Install

```bash
pip install rvcadence          # core scheduler, zero dependencies
pip install rvcadence[astro]   # + name/site resolution, visibility, lunar pollution avoidance (astropy)
```

## Quickstart

```python
from datetime import date
from rvcadence import plan_calendar

result = plan_calendar(
    n_obs=20,
    periods_d=9.53,
    season_start=date(2026, 5, 1),
    season_end=date(2027, 4, 30),
    rotation_period_d=12.45,
    windows="2026-05-01 to 2026-05-19; 2026-07-29 to 2027-04-30",
)
print(result.dates)
print(f"median gap: {result.median_gap_d} d, mean gap: {result.mean_gap_d} d")
```

For a multi-planet system, pass a list of periods — coverage is optimized
for the *worst-covered* planet at each step, not an average:

```python
result = plan_calendar(
    n_obs=20,
    periods_d=[9.53, 21.7],   # two known/candidate planets
    season_start=date(2026, 5, 1),
    season_end=date(2027, 4, 30),
)
```

With lunar avoidance (requires `pip install rvcadence[moon]`):

```python
import astropy.units as u
from astropy.coordinates import EarthLocation, SkyCoord

paranal = EarthLocation(lat=-24.6272 * u.deg, lon=-70.4039 * u.deg, height=2635 * u.m)
target = SkyCoord(ra=123.45 * u.deg, dec=-12.3 * u.deg)

result = plan_calendar(
    n_obs=20,
    periods_d=9.53,
    season_start=date(2026, 5, 1),
    season_end=date(2027, 4, 30),
    target_coord=target,
    observer_location=paranal,
    min_moon_sep_deg=30.0,
)
```

The default 30° threshold is a widely-used rule-of-thumb avoidance radius
against lunar scattered-light contamination in high-resolution spectroscopy;
override `min_moon_sep_deg` for a different instrument or tolerance. Nights
are evaluated at local solar midnight, sunset-labeled (the night of date `D`
runs from sunset on `D` to sunrise on `D+1`).

## How it works

Starting from the first and last available dates, the algorithm repeatedly
adds the candidate date that best fills gaps in planet-orbital-phase coverage
(and stellar-rotation-phase coverage, if known), weighted against how far it
is in time from already-selected dates. For multiple planets, phase coverage
is the *worst-case* across all periods — a candidate only scores well if it
improves coverage for whichever planet is currently least-covered, so one
well-phased planet can't mask a poorly-phased one:

```
score = 0.55 · d_planet_phase + 0.30 · d_rotation_phase + 0.15 · d_time_spread   (rotation period known)
score = 0.80 · d_planet_phase + 0.20 · d_time_spread                             (rotation period unknown)
```

See `examples/explainer/` for the full animated walkthrough (manim source +
rendered mp4) — the example imports its scoring logic directly from this
package (see `tests/test_explainer_example.py`), so it can't drift out of
sync with the real algorithm.

## Development

```bash
git clone <repo-url>
cd rvcadence
pip install -e ".[dev,astro]"
pytest
```

## License

MIT
