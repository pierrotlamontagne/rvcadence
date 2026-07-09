from __future__ import annotations

from datetime import date

_EMPTY_PLACEHOLDERS = {"", "na", "nan", "n/a", "none", "xxx", "tbd", "?"}


def parse_date_yyyy_mm_dd(s: str) -> date:
    s = s.strip()
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


def parse_obs_windows(text: str) -> list[tuple[date, date]]:
    """
    Parse a string like "2026-05-01 to 2026-08-18; 2026-12-19 to 2027-04-30"
    into a list of (start_date, end_date) tuples. Returns [] for empty/null
    inputs (including common placeholders like "XXX", "TBD", "?").
    """
    raw = str(text if text else "").strip()
    if raw.lower() in _EMPTY_PLACEHOLDERS:
        return []
    windows: list[tuple[date, date]] = []
    for part in raw.split(";"):
        p = part.strip()
        if not p:
            continue
        if " to " in p:
            a_str, b_str = p.split(" to ", 1)
            a = parse_date_yyyy_mm_dd(a_str)
            b = parse_date_yyyy_mm_dd(b_str)
        else:
            a = parse_date_yyyy_mm_dd(p)
            b = a
        if b < a:
            a, b = b, a
        windows.append((a, b))
    return windows


def build_allowed_offsets(
    season_start: date,
    season_end: date,
    windows: list[tuple[date, date]],
) -> list[int]:
    """
    Sorted list of integer day offsets (from season_start) that fall within at
    least one visibility window and within [season_start, season_end]. If
    windows is empty, the target is treated as observable all season.
    """
    if season_end < season_start:
        raise ValueError(f"season_end ({season_end}) is before season_start ({season_start})")
    if not windows:
        full_n_days = (season_end - season_start).days + 1
        return list(range(full_n_days))
    allowed: set[int] = set()
    for a, b in windows:
        lo = max(a, season_start)
        hi = min(b, season_end)
        if hi < lo:
            continue
        n = (hi - lo).days + 1
        start_offset = (lo - season_start).days
        for k in range(n):
            allowed.add(start_offset + k)
    return sorted(allowed)


def contiguous_ranges(sorted_values: list[int]) -> list[tuple[int, int]]:
    """Collapse a sorted list of ints into inclusive (start, end) runs."""
    if not sorted_values:
        return []
    out: list[tuple[int, int]] = []
    start = sorted_values[0]
    prev = sorted_values[0]
    for x in sorted_values[1:]:
        if x == prev + 1:
            prev = x
            continue
        out.append((start, prev))
        start = x
        prev = x
    out.append((start, prev))
    return out
