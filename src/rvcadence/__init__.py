from .windows import build_allowed_offsets, contiguous_ranges, parse_obs_windows
from .schedule import (
    CandidateScore,
    ScheduleResult,
    best_candidate,
    build_schedule,
    evaluate_candidate,
    plan_calendar,
    spacing_stats,
)

__all__ = [
    "parse_obs_windows",
    "build_allowed_offsets",
    "contiguous_ranges",
    "CandidateScore",
    "evaluate_candidate",
    "best_candidate",
    "build_schedule",
    "spacing_stats",
    "ScheduleResult",
    "plan_calendar",
]

try:
    from .moon import is_moon_polluted, moon_allowed_offsets, moon_coord_at_midnight

    __all__ += ["is_moon_polluted", "moon_allowed_offsets", "moon_coord_at_midnight"]
except ImportError:
    pass
