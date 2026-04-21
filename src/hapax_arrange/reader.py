"""Parse a MIDI file into abs-tick event lists plus metadata."""

from __future__ import annotations

from pathlib import Path

import mido

from hapax_arrange.errors import UnsupportedMidiTypeError
from hapax_arrange.model import Marker, ParsedMidi, SourceTrack
from hapax_arrange.timing import TSChange

DEFAULT_TEMPO_US = 500_000  # 120 BPM
DEFAULT_TS = (4, 4)


def parse(path: Path) -> ParsedMidi:
    mf = mido.MidiFile(path)
    if mf.type == 2:
        raise UnsupportedMidiTypeError(
            f"{path.name}: Type 2 MIDI files are not supported. Re-export as Type 1."
        )

    ppq = mf.ticks_per_beat
    initial_tempo_bpm: float | None = None
    initial_ts: tuple[int, int] | None = None
    ts_changes: list[TSChange] = []
    tempo_events_after_zero: list[int] = []
    markers: list[Marker] = []
    tracks: list[SourceTrack] = []
    total_length = 0

    for idx, track in enumerate(mf.tracks):
        abs_tick = 0
        track_name = f"Track {idx}"
        events: list[tuple[int, mido.Message | mido.MetaMessage]] = []
        saw_name = False
        for msg in track:
            abs_tick += msg.time
            if msg.is_meta:
                if msg.type == "set_tempo":
                    if abs_tick == 0 and initial_tempo_bpm is None:
                        initial_tempo_bpm = mido.tempo2bpm(msg.tempo)
                    elif abs_tick > 0:
                        tempo_events_after_zero.append(abs_tick)
                elif msg.type == "time_signature":
                    ts_changes.append(TSChange(abs_tick, msg.numerator, msg.denominator))
                    if initial_ts is None and abs_tick == 0:
                        initial_ts = (msg.numerator, msg.denominator)
                elif msg.type == "marker":
                    markers.append(Marker(abs_tick, msg.text))
                elif msg.type == "track_name" and not saw_name:
                    track_name = msg.name or track_name
                    saw_name = True
            events.append((abs_tick, msg))
        total_length = max(total_length, abs_tick)
        tracks.append(SourceTrack(index=idx, name=track_name, events=events))

    # Dedupe markers on (tick, name) — some DAWs write to multiple tracks.
    seen: set[tuple[int, str]] = set()
    unique_markers: list[Marker] = []
    for m in sorted(markers, key=lambda x: (x.tick, x.name)):
        key = (m.tick, m.name)
        if key in seen:
            continue
        seen.add(key)
        unique_markers.append(m)

    if initial_tempo_bpm is None:
        initial_tempo_bpm = mido.tempo2bpm(DEFAULT_TEMPO_US)
    if initial_ts is None:
        initial_ts = DEFAULT_TS

    ts_changes.sort(key=lambda c: c.tick)

    return ParsedMidi(
        ppq=ppq,
        initial_tempo_bpm=float(initial_tempo_bpm),
        initial_time_signature=initial_ts,
        ts_changes=ts_changes,
        tempo_events_after_zero=sorted(set(tempo_events_after_zero)),
        tracks=tracks,
        markers=unique_markers,
        total_length_ticks=total_length,
        midi_type=mf.type,
    )
