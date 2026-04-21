"""Per-track × per-section content extraction with boundary clamping."""

from __future__ import annotations

import mido

from hapax_arrange.model import PatternContent, SectionSpan, SourceTrack
from hapax_arrange.timing import TSChange, ticks_to_bars

# Meta events that should not be copied into per-pattern output (writer re-injects them).
_STRIPPED_METAS = frozenset({"set_tempo", "time_signature", "key_signature", "smpte_offset"})


def slice_all(
    tracks: list[SourceTrack],
    spans: list[SectionSpan],
    ppq: int,
    ts_changes: list[TSChange],
) -> list[PatternContent]:
    out: list[PatternContent] = []
    for track in tracks:
        for span in spans:
            out.append(_slice_one(track, span, ppq, ts_changes))
    return out


def _slice_one(
    track: SourceTrack,
    span: SectionSpan,
    ppq: int,
    ts_changes: list[TSChange],
) -> PatternContent:
    length_ticks = span.end_tick - span.start_tick
    span_end_rel = length_ticks  # note-off-at-end cap; clamp to span_end_rel - 1 for safety

    # Snapshot which (channel, note) pairs are still held going into the section.
    # Note-offs at exactly span.start_tick close out notes from the prior section and
    # are NOT carried into this section's state.
    held_before: dict[tuple[int, int], bool] = {}
    for abs_tick, msg in track.events:
        if msg.is_meta:
            if abs_tick > span.start_tick:
                break
            continue
        if _is_note_off(msg) and abs_tick <= span.start_tick:
            held_before[(msg.channel, msg.note)] = False
            continue
        if abs_tick >= span.start_tick:
            break
        if _is_note_on(msg):
            held_before[(msg.channel, msg.note)] = True
        elif _is_note_off(msg):
            held_before[(msg.channel, msg.note)] = False

    # Walk the section: [start, end) for most events; (start, end] for note_offs
    # so that a note ending exactly at the boundary closes cleanly in this section.
    sliced: list[tuple[int, mido.Message | mido.MetaMessage]] = []
    open_notes: dict[tuple[int, int], int] = {}
    stray_offs = 0

    for abs_tick, msg in track.events:
        note_off = not msg.is_meta and _is_note_off(msg)
        if note_off:
            if abs_tick <= span.start_tick:
                continue
            if abs_tick > span.end_tick:
                break
        else:
            if abs_tick < span.start_tick:
                continue
            if abs_tick >= span.end_tick:
                break
        rel = min(abs_tick - span.start_tick, length_ticks)
        if msg.is_meta:
            if msg.type in _STRIPPED_METAS:
                continue
            if msg.type == "marker":
                continue
            if msg.type == "track_name":
                continue  # writer re-injects
            if msg.type == "end_of_track":
                continue
            sliced.append((rel, msg))
            continue

        if _is_note_on(msg):
            key = (msg.channel, msg.note)
            open_notes[key] = rel
            sliced.append((rel, msg))
        elif _is_note_off(msg):
            key = (msg.channel, msg.note)
            if key in open_notes:
                sliced.append((rel, msg))
                del open_notes[key]
            elif held_before.get(key):
                # A note-off whose note-on was in a previous section: drop.
                stray_offs += 1
                held_before[key] = False
            else:
                # Unpaired off with no prior on — drop silently.
                stray_offs += 1
        else:
            sliced.append((rel, msg))

    # Clamp any remaining open notes at span end.
    clamp_tick = max(0, span_end_rel - 1)
    clamped = 0
    for (ch, note), _on_rel in open_notes.items():
        sliced.append((clamp_tick, mido.Message("note_off", channel=ch, note=note, velocity=0)))
        clamped += 1

    sliced.sort(key=lambda e: (e[0], _priority(e[1])))

    length_bars = ticks_to_bars(span.start_tick, length_ticks, ppq, ts_changes)

    return PatternContent(
        track_id=track.index,
        track_name=track.name,
        section_name=span.name,
        events=tuple(sliced),
        length_ticks=length_ticks,
        length_bars=length_bars,
        clamped_notes=clamped,
        stray_note_offs=stray_offs,
    )


def _is_note_on(msg: mido.Message | mido.MetaMessage) -> bool:
    return not msg.is_meta and msg.type == "note_on" and getattr(msg, "velocity", 0) > 0


def _is_note_off(msg: mido.Message | mido.MetaMessage) -> bool:
    if msg.is_meta:
        return False
    if msg.type == "note_off":
        return True
    # running-status zero-velocity note-on is note-off
    return msg.type == "note_on" and getattr(msg, "velocity", 0) == 0


def _priority(msg: mido.Message | mido.MetaMessage) -> int:
    if msg.is_meta:
        return 0
    if _is_note_off(msg):
        return 1
    if _is_note_on(msg):
        return 3
    return 2  # CC, pitchbend, etc between offs and ons
