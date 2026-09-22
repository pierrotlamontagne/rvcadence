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
pip install rvcadence
```

That's the whole install: scheduler, name/site resolution, visibility and
lunar avoidance (astropy), and ready-made figures (matplotlib).

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
instead of hand-typing windows:

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

For a multi-planet system, pass a list of periods. Coverage is optimized
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

Mid-campaign, pass the epochs already taken via `existing_times`. They lock
in place, only `n_obs - len(existing)` further dates get chosen, and new
dates always fall after the last observed epoch: rvcadence never schedules
in the past.

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

`existing_times` accepts `datetime.date`/`datetime`, ISO-8601 strings,
JD/MJD floats, an `astropy.time.Time`, an `astropy.table.Column`, or an
`astropy.table.Table` (time column auto-detected from
`time`/`bjd`/`jd`/`mjd`/`date`, or set via `time_column=`).

Bare floats above 2.4e6 are read as JD, at or below as MJD.
**RJD (`JD - 2400000.0`) must declare itself via `time_format="rjd"`.** MJD
and RJD are numerically indistinguishable (both ~61000 in 2026, 0.5 d apart),
so reading RJD as MJD silently shifts an observation onto the wrong night.
`time_format="jd"`/`"mjd"` exist for the same reason.

The cutoff defaults to the day after your last observation. If there's a gap
(you observed through May, it's now August), pass `schedule_from` explicitly,
since no locked epoch can otherwise tell the scheduler June and July are gone.

```python
result = plan_calendar(
    n_obs=20,
    periods_d=9.53,
    season_start=date(2026, 5, 1),
    season_end=date(2027, 4, 30),
    existing_times=["2026-05-03", "2026-05-19"],
    schedule_from=date(2026, 8, 1),   # planning resumes here, not after 05-19
)
print(result.n_unscheduled)   # epochs that no longer fit before season_end
```

`schedule_from` works with or without `existing_times`. If surviving nights
can't fit every epoch, `n_unscheduled` reports the shortfall instead of
raising: an over-subscribed programme is a fact, not an error.

Epochs before `season_start` stay locked and keep the schedule phased, but
`median_gap_d`/`mean_gap_d` are computed only within
`[season_start, season_end]`. Same-night observations collapse to one epoch.

### Composable constraints

`windows` text, lunar avoidance, and astropy-computed visibility are
independent, composable constraints. Any subset may be supplied, and
supplied constraints **intersect**:

- `windows`: manually-specified date ranges (string or pre-parsed list).
- `min_moon_sep_deg` (needs `target_coord` + `observer_location`): excludes
  nights where the Moon is within this separation of the target, evaluated
  at local solar midnight. Default 30°, the standard avoidance radius against
  lunar scattered light in high-resolution spectroscopy. Pass `None` to
  disable. Nights are sunset-labeled (date `D` runs sunset on `D` to sunrise
  on `D+1`).
- `min_altitude_deg` (needs `target_coord` + `observer_location`): excludes
  nights where the target doesn't clear this altitude while the Sun is below
  `twilight_sun_alt_deg` (default -18°), both evaluated **at the target's
  transit time**, not midnight, since a midnight-only check could wrongly
  exclude a target that transits at 9pm on a perfectly observable night. Off
  by default, since no altitude is universally correct.

`target_coord`/`observer_location` accept resolved astropy objects
(`SkyCoord`/`EarthLocation`) or plain name strings, resolved once per call
and printed for confirmation.

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
adds the candidate that best fills gaps in planet-orbital-phase coverage (and
rotation-phase coverage, if known), weighted by distance from already-selected
dates. For multiple planets, coverage is the *worst-case* across all periods,
so one well-phased planet can't mask a poorly-phased one:

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
    weights=(0.70, 0.20, 0.10),   # (planet, rotation, time), or (planet, time) without a rotation period
    planet_weights=[0.75, 0.25],  # prioritise the first planet's phase coverage
)
```

`weights` must be non-negative and sum to 1 (three entries with
`rotation_period_d`, two without). It is never silently renormalised: a
vector that doesn't sum to 1 raises `ValueError`.

`planet_weights` changes how the planet-phase term aggregates across periods:

| `planet_weights` | aggregation |
|------------------|-------------|
| `None` (default) | `min` over the periods, worst-case |
| a sequence summing to 1 | priority-weighted mean over the periods |

**Opting into `planet_weights` trades away the worst-case guarantee.** Under
a weighted mean, a high-weight planet with good coverage can pull the score
up while a low-weight planet's coverage stays poor. Use it only with a
genuine priority ordering among the planets.

See `examples/explainer/` for the animated walkthrough (manim source + mp4).
Its scoring logic imports directly from this package
(`tests/test_explainer_example.py`), so it can't drift from the real
algorithm. `examples/quickstart_demo.ipynb` walks every example above
visually via `rvcadence.plotting`.

## Plotting

`rvcadence.plotting` turns a `ScheduleResult` into the figures you would
otherwise hand-code.

```python
import matplotlib.pyplot as plt
from rvcadence.plotting import plot_summary, plot_timeline

plot_timeline(result, windows=[(date(2026, 5, 1), date(2026, 5, 19))])
plt.show()

plot_summary(result)   # timeline, night availability, phase coverage, coverage vs. N
plt.show()
```

Every function takes the result first, draws into an `ax=` you supply (or
creates its own figure), and returns the Axes, so they compose into any
layout. Already-observed epochs get their own colour and legend entry in
every date-bearing figure.

| Function | Shows | Needs |
|----------|-------|-------|
| `plot_timeline` | scheduled dates across the season, windows shaded | `[plot]` |
| `plot_phase_coverage` | orbital phase of each epoch, one row per planet | `[plot]` |
| `plot_night_availability` | which nights pass the constraints, and which are picked | `[plot]` |
| `plot_constraint_breakdown` | how many nights each constraint leaves | `[plot]` |
| `plot_greedy_vs_random` | phase histogram against randomly drawn nights | `[plot]` |
| `plot_phase_vs_rotation_phase` | whether the cadence aliases planet onto activity | `[plot]` |
| `plot_coverage_vs_n` | largest phase gap versus number of epochs | `[plot]` |
| `plot_summary` | four-panel dashboard of the above | `[plot]` |
| `plot_staralt` | airmass by night and time-of-night | `[plot]`, `[astro]` |
| `plot_altitude_sensitivity` | visible nights versus the altitude cut | `[plot]`, `[astro]` |

## Development

```bash
git clone <repo-url>
cd rvcadence
pip install -e ".[dev,astro]"
pytest
```

## License

MIT
