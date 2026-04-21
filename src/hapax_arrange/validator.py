"""Hapax constraint checks. Returns (warnings, errors) without mutating input."""

from __future__ import annotations

from hapax_arrange.model import Arrangement, ParsedMidi, SourceTrack

MAX_TRACKS = 16
MAX_SLOTS_PER_TRACK = 16
GM_DRUM_CHANNEL = 9  # 0-indexed


def check(
    arrangement: Arrangement,
    parsed: ParsedMidi,
    source_tracks: list[SourceTrack],
    *,
    max_bars: int = 32,
    drum_ids: set[int] | None = None,
) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    drum_ids = drum_ids or set()

    # Track count
    if len(arrangement.tracks) > MAX_TRACKS:
        errors.append(f"Track count {len(arrangement.tracks)} exceeds Hapax limit of {MAX_TRACKS}.")

    # Per-track slot count and per-pattern length
    for hapax_track, slots in arrangement.pattern_slots.items():
        if len(slots) > MAX_SLOTS_PER_TRACK:
            errors.append(
                f"Track T{hapax_track:02d} has {len(slots)} unique patterns; "
                f"Hapax limit is {MAX_SLOTS_PER_TRACK} per track."
            )
        for slot in slots:
            if slot.length_bars > max_bars:
                warnings.append(
                    f"T{hapax_track:02d} P{slot.slot_index:02d} is "
                    f"{slot.length_bars:.2f} bars (>{max_bars}); "
                    f"Hapax will truncate on import."
                )
            if slot.source_content.clamped_notes:
                warnings.append(
                    f"T{hapax_track:02d} P{slot.slot_index:02d}: "
                    f"{slot.source_content.clamped_notes} note(s) clamped to section end."
                )
            if slot.source_content.stray_note_offs:
                warnings.append(
                    f"T{hapax_track:02d} P{slot.slot_index:02d}: "
                    f"{slot.source_content.stray_note_offs} stray note-off(s) dropped."
                )

    # Tempo events after tick 0
    if parsed.tempo_events_after_zero:
        warnings.append(
            f"Tempo change(s) at tick(s) {parsed.tempo_events_after_zero} — "
            f"Hapax tempo is project-level; only the initial tempo is used."
        )

    # Time-signature handling
    if len(parsed.ts_changes) > 1:
        warnings.append(
            f"Time signature changes at {[c.tick for c in parsed.ts_changes[1:]]} — "
            f"bar counts are aggregated across segments; emitted patterns use the initial TS."
        )
    elif parsed.initial_time_signature != (4, 4):
        warnings.append(f"Non-4/4 time signature {parsed.initial_time_signature}.")

    # Per source track: channel check, drum heuristic, zero-note detection
    by_id = {t.index: t for t in source_tracks}
    for tm in arrangement.tracks:
        src = by_id.get(tm.source_track)
        if src is None:
            continue
        channels = {m.channel for _, m in src.events if not m.is_meta and hasattr(m, "channel")}
        note_count = sum(
            1 for _, m in src.events if not m.is_meta and m.type in ("note_on", "note_off")
        )
        if note_count == 0:
            warnings.append(f"T{tm.hapax_track:02d} '{tm.name}' has no notes.")
        if len(channels) > 3:
            warnings.append(
                f"T{tm.hapax_track:02d} '{tm.name}' uses {len(channels)} MIDI channels — "
                f"Hapax does not support MPE/per-note channel on import."
            )
        if tm.kind != "drum" and tm.source_track not in drum_ids and GM_DRUM_CHANNEL in channels:
            warnings.append(
                f"T{tm.hapax_track:02d} '{tm.name}' uses MIDI channel 10 (GM drums) but was "
                f"not flagged with --drums {tm.source_track}; drum lane labels won't be set."
            )

    return warnings, errors
