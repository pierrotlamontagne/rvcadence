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

Or let `rvcadence` compute visibility itself, from a target name and site,
instead of hand-typing windows (requires `pip install rvcadence[astro]`):

```python
result = plan_calendar(
    n_obs=20,
    periods_d=9.53,
    season_start=date(2026, 5, 1),
    season_end=date(2027, 4, 30),
    target_coord="K2-182",
    observer_location="Paranal Observatory",
    min_altitude_deg=30.0,
)
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

### Already-observed epochs

Mid-campaign, pass the epochs you have already taken. They are locked in
place, excluded from the candidate pool, and only `n_obs - len(existing)`
further dates are chosen — so you get an updated calendar for what remains,
phased against what you already have.

```python
result = plan_calendar(
    n_obs=20,                       # total for the programme, not the remainder
    periods_d=9.53,
    season_start=date(2026, 5, 1),
    season_end=date(2027, 4, 30),
    existing_times=["2026-05-03", "2026-05-19", "2026-06-02"],
)
print(result.n_remaining)     # 17
print(result.locked_dates)    # the three epochs above
print(result.new_dates)       # the 17 newly scheduled dates
print(result.dates)           # sorted union of both
```

`existing_times` accepts a sequence of `datetime.date`/`datetime`, ISO-8601
strings, or JD/MJD floats; an `astropy.time.Time`; an `astropy.table.Column`;
or an `astropy.table.Table` whose time column is picked automatically from
`time`/`bjd`/`jd`/`mjd`/`date` (case-insensitive), or named with
`time_column=`.

Bare floats above 2.4e6 are read as JD, at or below it as MJD.
**RJD (`JD - 2400000.0`) must declare itself with `time_format="rjd"`.** MJD
and RJD are numerically indistinguishable — in 2026 both are near 61000 and
they differ by only 0.5 d — so no magnitude test can tell them apart. Read as
MJD, an RJD number reconstructs a JD half a day later than the true epoch, so
the observation can be placed on the following day. `time_format="jd"` and
`"mjd"` are available for the same reason.

Epochs before `season_start` are fine: they stay locked and keep the schedule
phased against them, and `median_gap_d`/`mean_gap_d` are reported over the
epochs inside `[season_start, season_end]` so they always describe the
cadence across the season you are planning. Multiple observations on the same
night collapse to one epoch — a night is the scheduler's unit.

### Composable constraints

`windows` text, lunar avoidance, and astropy-computed visibility are
independent, composable constraints — any subset may be supplied, and
supplied constraints **intersect**:

- `windows`: manually-specified date ranges (string or pre-parsed list).
- `min_moon_sep_deg` (needs `target_coord` + `observer_location`): excludes
  nights where the Moon is within this separation of the target, evaluated
  at local solar midnight. Default 30°, a widely-used rule-of-thumb
  avoidance radius against lunar scattered-light contamination in
  high-resolution spectroscopy; pass `None` to disable even when a target is
  given. Nights are sunset-labeled (the night of date `D` runs from sunset
  on `D` to sunrise on `D+1`).
- `min_altitude_deg` (needs `target_coord` + `observer_location`): excludes
  nights where the target doesn't clear this altitude, AND the Sun isn't
  below `twilight_sun_alt_deg` (default -18°, astronomical twilight), both
  evaluated **at the target's transit (culmination) time** that night — not
  local midnight. This deliberately differs from the moon check: for the
  Moon, midnight-vs-transit is negligible, but for target altitude it would
  be a real correctness bug (a target transiting at 9pm could be wrongly
  excluded by a midnight-only check on a night it's perfectly observable).
  Off by default (`None`) — there is no universally correct altitude.

`target_coord`/`observer_location` accept either already-resolved astropy
objects (`SkyCoord`/`EarthLocation`) or plain name strings — a string is
resolved once per call (CDS Sesame / astropy's site registry) and the
resolved value is printed for confirmation.

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
    min_altitude_deg=30.0,
)
```

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

### Tuning the score

Both the outer weights and the multi-planet aggregation are adjustable.

```python
result = plan_calendar(
    n_obs=20,
    periods_d=[9.53, 21.7],
    season_start=date(2026, 5, 1),
    season_end=date(2027, 4, 30),
    rotation_period_d=12.45,
    weights=(0.70, 0.20, 0.10),   # (planet, rotation, time); (planet, time) without a rotation period
    planet_weights=[0.75, 0.25],  # prioritise the first planet's phase coverage
)
```

`weights` must be non-negative and sum to 1, with three entries when
`rotation_period_d` is given and two when it is not. It is never silently
renormalised — a vector that does not sum to 1 raises `ValueError`.

`planet_weights` changes how the planet-phase term aggregates across periods:

| `planet_weights` | aggregation |
|------------------|-------------|
| `None` (default) | `d_planet_phase = min` over the periods — worst-case |
| a sequence summing to 1 | `d_planet_phase = ` priority-weighted mean over the periods |

**Opting into `planet_weights` trades the worst-case guarantee away.** The
default `min` aggregation exists precisely so that one well-covered planet
cannot mask a poorly-covered one. Under a weighted mean it can: a high-weight
planet with good coverage will pull the score up even while a low-weight
planet's phase coverage stays poor. Use it when you genuinely have a priority
ordering among the planets, not as a default flavour.

See `examples/explainer/` for the full animated walkthrough (manim source +
rendered mp4) — the example imports its scoring logic directly from this
package (see `tests/test_explainer_example.py`), so it can't drift out of
sync with the real algorithm.

See `examples/quickstart_demo.ipynb` for a runnable, visual walkthrough of
every example above plus a target-visibility calendar, a breakdown of how
much each constraint (windows/moon/altitude) removes on its own, and two
bonus diagnostics (altitude-threshold sensitivity, greedy vs. random phase
coverage). Needs `pip install rvcadence[astro] matplotlib` to run.

## Development

```bash
git clone <repo-url>
cd rvcadence
pip install -e ".[dev,astro]"
pytest
```

## License

MIT
