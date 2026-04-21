"""Turn a flat marker list into a contiguous list of SectionSpans."""

from __future__ import annotations

from collections import Counter

from hapax_arrange.errors import NoMarkersError
from hapax_arrange.model import Marker, SectionSpan


def segment(markers: list[Marker], total_length_ticks: int) -> list[SectionSpan]:
    if not markers:
        raise NoMarkersError(
            "Input MIDI has no marker meta events. Add markers in your DAW to delimit "
            "sections (Intro, Verse, Chorus, ...) and re-export."
        )
    if total_length_ticks <= 0:
        raise NoMarkersError("Input MIDI has no content (zero length).")

    in_range = [m for m in markers if m.tick < total_length_ticks]
    if not in_range:
        raise NoMarkersError(
            "All markers are past the end of the MIDI file — none of them delimit any content."
        )
    sorted_markers = sorted(in_range, key=lambda m: m.tick)

    # Prepend implicit start-at-0 if needed.
    if sorted_markers[0].tick > 0:
        sorted_markers = [Marker(0, "Section 1"), *sorted_markers]

    # Collapse markers at the same tick by keeping the first.
    deduped: list[Marker] = []
    last_tick = -1
    for m in sorted_markers:
        if m.tick == last_tick:
            continue
        deduped.append(m)
        last_tick = m.tick

    # Rename duplicates: Verse, Verse, Verse -> Verse 1, Verse 2, Verse 3 (only on collision).
    renamed = _rename_duplicates([m.name for m in deduped])

    spans: list[SectionSpan] = []
    for i, m in enumerate(deduped):
        end = deduped[i + 1].tick if i + 1 < len(deduped) else total_length_ticks
        if end <= m.tick:
            continue
        spans.append(SectionSpan(name=renamed[i], start_tick=m.tick, end_tick=end))

    if not spans:
        raise NoMarkersError("All markers are past the end of the MIDI file.")
    return spans


def _rename_duplicates(names: list[str]) -> list[str]:
    counts = Counter(names)
    running: dict[str, int] = {}
    result: list[str] = []
    for name in names:
        if counts[name] == 1:
            result.append(name)
        else:
            running[name] = running.get(name, 0) + 1
            result.append(f"{name} {running[name]}")
    return result
