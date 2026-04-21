"""Tick <-> bar math, time-signature aware."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TSChange:
    tick: int
    numerator: int
    denominator: int


def ticks_per_bar(ppq: int, numerator: int, denominator: int) -> float:
    return ppq * 4 * (numerator / denominator)


def ticks_to_bars(
    start_tick: int,
    length_ticks: int,
    ppq: int,
    ts_changes: list[TSChange],
) -> float:
    """Piecewise bar count for [start_tick, start_tick + length_ticks).

    Walks every TS segment intersecting the window, summing overlap / ticks_per_bar(seg_ts).
    """
    if length_ticks <= 0:
        return 0.0

    end_tick = start_tick + length_ticks
    segments = _ts_segments(ts_changes)
    total_bars = 0.0
    for seg_start, seg_end, ts in segments:
        overlap_start = max(seg_start, start_tick)
        overlap_end = min(seg_end, end_tick) if seg_end is not None else end_tick
        if overlap_end <= overlap_start:
            continue
        overlap = overlap_end - overlap_start
        tpb = ticks_per_bar(ppq, ts.numerator, ts.denominator)
        total_bars += overlap / tpb
    return total_bars


def _ts_segments(
    ts_changes: list[TSChange],
) -> list[tuple[int, int | None, TSChange]]:
    """Yield (segment_start, segment_end_exclusive_or_None, ts) for each TS segment.

    If ts_changes is empty, falls back to one open-ended 4/4 segment starting at 0.
    If the first change starts after 0, prepends an implicit 4/4 segment at the head.
    """
    if not ts_changes:
        return [(0, None, TSChange(0, 4, 4))]

    changes = sorted(ts_changes, key=lambda c: c.tick)
    segments: list[tuple[int, int | None, TSChange]] = []
    if changes[0].tick > 0:
        segments.append((0, changes[0].tick, TSChange(0, 4, 4)))
    for i, change in enumerate(changes):
        end = changes[i + 1].tick if i + 1 < len(changes) else None
        segments.append((change.tick, end, change))
    return segments
