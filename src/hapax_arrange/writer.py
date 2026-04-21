"""Emit per-slot single-track Type 0 MIDI files."""

from __future__ import annotations

import re
from pathlib import Path

import mido

from hapax_arrange.model import Arrangement, PatternSlot

# Hapax §6.8 default drum lane labels. Track-name meta in this dot-separated form
# makes Hapax auto-label the drum lanes on import.
DRUM_LANE_LABELS = "KICK.SNARE.CLOSED HH.OPEN HH.LOW TOM.HI TOM.HAND CLAP.COWBELL"


def write(arrangement: Arrangement, outdir: Path, *, force: bool = False) -> list[Path]:
    midi_dir = outdir / "MIDI"
    _prepare_dir(midi_dir, force=force)

    paths: list[Path] = []
    for hapax_track in sorted(arrangement.pattern_slots.keys()):
        track_map = next(t for t in arrangement.tracks if t.hapax_track == hapax_track)
        for slot in arrangement.pattern_slots[hapax_track]:
            label = _track_name(track_map.kind, slot)
            path = midi_dir / _filename(hapax_track, slot)
            _write_slot(path, slot, arrangement, label)
            paths.append(path)
    return paths


def _prepare_dir(midi_dir: Path, *, force: bool) -> None:
    if midi_dir.exists() and any(midi_dir.iterdir()) and not force:
        raise FileExistsError(f"{midi_dir} is not empty. Use --force to overwrite.")
    midi_dir.mkdir(parents=True, exist_ok=True)
    if force:
        for child in midi_dir.iterdir():
            if child.is_file():
                child.unlink()


def _track_name(kind: str, slot: PatternSlot) -> str:
    if kind == "drum":
        return DRUM_LANE_LABELS
    raw = f"{slot.source_content.track_name} - {slot.sections_using[0]}"
    return raw.encode("latin-1", errors="replace").decode("latin-1")


def _filename(hapax_track: int, slot: PatternSlot) -> str:
    safe = _sanitize(slot.sections_using[0])
    return f"T{hapax_track:02d}_P{slot.slot_index:02d}_{safe}.mid"


def _sanitize(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
    return cleaned[:30] or "Section"


def _write_slot(path: Path, slot: PatternSlot, arrangement: Arrangement, track_name: str) -> None:
    mf = mido.MidiFile(type=0, ticks_per_beat=arrangement.ppq)
    track = mido.MidiTrack()
    mf.tracks.append(track)

    # Head meta at tick 0
    head: list[tuple[int, mido.Message | mido.MetaMessage]] = [
        (0, mido.MetaMessage("track_name", name=track_name)),
        (
            0,
            mido.MetaMessage(
                "time_signature",
                numerator=arrangement.time_signature[0],
                denominator=arrangement.time_signature[1],
            ),
        ),
        (0, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(arrangement.tempo_bpm))),
    ]
    # Body (rel ticks already)
    body: list[tuple[int, mido.Message | mido.MetaMessage]] = list(slot.source_content.events)
    all_events = head + body
    all_events.sort(key=lambda e: (e[0], _priority(e[1])))

    prev = 0
    for abs_tick, msg in all_events:
        delta = max(0, abs_tick - prev)
        track.append(msg.copy(time=delta))
        prev = abs_tick

    # Trailer: end_of_track pinned to slot length so trailing silence is preserved.
    trailing_delta = max(0, slot.length_ticks - prev)
    track.append(mido.MetaMessage("end_of_track", time=trailing_delta))

    mf.save(path)


def _priority(msg: mido.Message | mido.MetaMessage) -> int:
    if msg.is_meta:
        return 0
    if msg.type == "note_off" or (msg.type == "note_on" and getattr(msg, "velocity", 0) == 0):
        return 1
    if msg.type == "note_on":
        return 3
    return 2
