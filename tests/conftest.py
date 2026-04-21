"""Synthesized MIDI fixtures for the hapax-arrange test suite.

Every fixture builds a MidiFile programmatically so that test intent is visible in code
rather than hiding inside binary blobs.
"""

from __future__ import annotations

from pathlib import Path

import mido
import pytest

TrackEvents = list[tuple[int, "mido.Message | mido.MetaMessage"]]  # (abs_tick, msg)
Markers = list[tuple[int, str]]


def make_midi(
    path: Path,
    tracks: list[TrackEvents],
    markers: Markers | None = None,
    *,
    track_names: list[str] | None = None,
    ppq: int = 480,
    tempo_bpm: float = 120.0,
    ts: tuple[int, int] = (4, 4),
    midi_type: int = 1,
) -> Path:
    """Build a MIDI file from abs-tick event lists and save it to `path`.

    - `tracks` is a list of lists of (abs_tick, message) pairs per track.
    - `markers` go onto a dedicated conductor track (index 0) for Type 1,
      or merged into the single track for Type 0.
    - Tempo/TS meta events are auto-emitted at tick 0 of the conductor track.
    """
    markers = markers or []
    track_names = track_names or [f"Track {i}" for i in range(len(tracks))]
    mf = mido.MidiFile(type=midi_type, ticks_per_beat=ppq)

    if midi_type == 1:
        conductor = mido.MidiTrack()
        conductor_events: TrackEvents = [
            (0, mido.MetaMessage("track_name", name="conductor")),
            (0, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(tempo_bpm))),
            (0, mido.MetaMessage("time_signature", numerator=ts[0], denominator=ts[1])),
        ]
        for tick, name in markers:
            conductor_events.append((tick, mido.MetaMessage("marker", text=name)))
        _fill_track(conductor, conductor_events)
        mf.tracks.append(conductor)

        for name, events in zip(track_names, tracks, strict=False):
            track = mido.MidiTrack()
            head: TrackEvents = [(0, mido.MetaMessage("track_name", name=name))]
            _fill_track(track, head + events)
            mf.tracks.append(track)
    else:
        track = mido.MidiTrack()
        name = track_names[0] if track_names else "Track 0"
        head = [
            (0, mido.MetaMessage("track_name", name=name)),
            (0, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(tempo_bpm))),
            (0, mido.MetaMessage("time_signature", numerator=ts[0], denominator=ts[1])),
        ]
        merged = list(tracks[0]) if tracks else []
        for tick, mname in markers:
            merged.append((tick, mido.MetaMessage("marker", text=mname)))
        _fill_track(track, head + merged)
        mf.tracks.append(track)

    mf.save(path)
    return path


def _fill_track(track: mido.MidiTrack, events: TrackEvents) -> None:
    sorted_events = sorted(events, key=lambda e: (e[0], _priority(e[1])))
    prev = 0
    for abs_tick, msg in sorted_events:
        delta = max(0, abs_tick - prev)
        track.append(msg.copy(time=delta))
        prev = abs_tick


def _priority(msg: mido.Message | mido.MetaMessage) -> int:
    # meta first, then note_off, then everything else at same tick
    if msg.is_meta:
        return 0
    if msg.type == "note_off" or (msg.type == "note_on" and getattr(msg, "velocity", 0) == 0):
        return 1
    return 2


def notes(
    channel: int,
    pitch: int,
    *,
    start: int,
    dur: int,
    velocity: int = 100,
) -> TrackEvents:
    """Return a single note as (start, note_on) and (start+dur, note_off)."""
    return [
        (start, mido.Message("note_on", channel=channel, note=pitch, velocity=velocity)),
        (
            start + dur,
            mido.Message("note_off", channel=channel, note=pitch, velocity=0),
        ),
    ]


BAR_4_4 = 480 * 4  # one bar at ppq=480, 4/4


@pytest.fixture
def simple_intro_verse_chorus(tmp_path: Path) -> Path:
    """3 sections (Intro=8b, Verse=8b, Chorus=8b), one track with a unique note per section."""
    ppq = 480
    bar = ppq * 4
    events: TrackEvents = []
    events += notes(0, 60, start=0, dur=bar)  # Intro: C4
    events += notes(0, 62, start=8 * bar, dur=bar)  # Verse: D4
    events += notes(0, 64, start=16 * bar, dur=bar)  # Chorus: E4
    # Hold the timeline open to 24 bars
    events += notes(0, 60, start=23 * bar, dur=bar // 4, velocity=1)
    return make_midi(
        tmp_path / "simple.mid",
        tracks=[events],
        markers=[(0, "Intro"), (8 * bar, "Verse"), (16 * bar, "Chorus")],
        track_names=["Lead"],
        ppq=ppq,
    )


@pytest.fixture
def verse_chorus_verse_chorus(tmp_path: Path) -> Path:
    """4 sections where V1==V2 and C1==C2; expect 2 slots after dedup."""
    ppq = 480
    bar = ppq * 4
    # Verse content: one 4-bar phrase
    verse_phrase: TrackEvents = []
    for i in range(4):
        verse_phrase += notes(0, 60 + i, start=i * bar, dur=bar)
    # Chorus content: one 4-bar phrase, different notes
    chorus_phrase: TrackEvents = []
    for i in range(4):
        chorus_phrase += notes(0, 67 + i, start=i * bar, dur=bar)

    events: TrackEvents = []
    # Verse 1 at bar 0, Chorus 1 at bar 4, Verse 2 at bar 8, Chorus 2 at bar 12
    for i, ev in enumerate([verse_phrase, chorus_phrase, verse_phrase, chorus_phrase]):
        offset = i * 4 * bar
        for tick, msg in ev:
            events.append((tick + offset, msg))
    return make_midi(
        tmp_path / "vcvc.mid",
        tracks=[events],
        markers=[
            (0, "Verse"),
            (4 * bar, "Chorus"),
            (8 * bar, "Verse"),
            (12 * bar, "Chorus"),
        ],
        track_names=["Lead"],
        ppq=ppq,
    )


@pytest.fixture
def no_markers_midi(tmp_path: Path) -> Path:
    """Valid MIDI with zero markers — should trigger NoMarkersError."""
    ppq = 480
    bar = ppq * 4
    return make_midi(
        tmp_path / "no_markers.mid",
        tracks=[notes(0, 60, start=0, dur=bar)],
        markers=[],
        ppq=ppq,
    )


@pytest.fixture
def type2_midi(tmp_path: Path) -> Path:
    """Hand-roll a Type 2 file — should raise UnsupportedMidiTypeError."""
    path = tmp_path / "type2.mid"
    mf = mido.MidiFile(type=2, ticks_per_beat=480)
    mf.tracks.append(mido.MidiTrack())
    mf.save(path)
    return path


@pytest.fixture
def long_section_over_32_bars(tmp_path: Path) -> Path:
    """One 36-bar section — must trigger the >max-bars warning."""
    ppq = 480
    bar = ppq * 4
    events: TrackEvents = []
    for i in range(36):
        events += notes(0, 60 + (i % 12), start=i * bar, dur=bar)
    return make_midi(
        tmp_path / "long.mid",
        tracks=[events],
        markers=[(0, "LongSection")],
        track_names=["Lead"],
        ppq=ppq,
    )


@pytest.fixture
def drums_with_lane_names(tmp_path: Path) -> Path:
    """Drum track on channel 10 (0-indexed 9) using GM kick/snare/hh notes."""
    ppq = 480
    bar = ppq * 4
    events: TrackEvents = []
    # Kick on beats 1,3; snare on 2,4; closed HH every 8th
    for b in range(4):
        events.append((b * bar, mido.Message("note_on", channel=9, note=36, velocity=110)))
        events.append(
            (b * bar + ppq // 4, mido.Message("note_off", channel=9, note=36, velocity=0))
        )
        events.append(
            (b * bar + ppq * 2, mido.Message("note_on", channel=9, note=38, velocity=100))
        )
        events.append(
            (b * bar + ppq * 2 + ppq // 4, mido.Message("note_off", channel=9, note=38, velocity=0))
        )
        for e in range(8):
            events.append(
                (b * bar + e * ppq // 2, mido.Message("note_on", channel=9, note=42, velocity=60))
            )
            events.append(
                (
                    b * bar + e * ppq // 2 + ppq // 8,
                    mido.Message("note_off", channel=9, note=42, velocity=0),
                )
            )
    return make_midi(
        tmp_path / "drums.mid",
        tracks=[events],
        markers=[(0, "Groove")],
        track_names=["Drums"],
        ppq=ppq,
    )


@pytest.fixture
def tempo_change_midfile(tmp_path: Path) -> Path:
    """Tempo change at bar 4 — validator should warn."""
    path = tmp_path / "tempo_change.mid"
    ppq = 480
    bar = ppq * 4
    mf = mido.MidiFile(type=1, ticks_per_beat=ppq)
    conductor = mido.MidiTrack()
    conductor.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(120), time=0))
    conductor.append(mido.MetaMessage("marker", text="A", time=0))
    conductor.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(140), time=4 * bar))
    conductor.append(mido.MetaMessage("marker", text="B", time=4 * bar))
    mf.tracks.append(conductor)
    data = mido.MidiTrack()
    data.append(mido.MetaMessage("track_name", name="Lead", time=0))
    data.append(mido.Message("note_on", note=60, velocity=100, time=0))
    data.append(mido.Message("note_off", note=60, velocity=0, time=8 * bar))
    mf.tracks.append(data)
    mf.save(path)
    return path


@pytest.fixture
def ts_change_midfile(tmp_path: Path) -> Path:
    """4/4 for 8 bars, then 3/4 for 4 bars — validator warns, bar math stays correct."""
    path = tmp_path / "ts_change.mid"
    ppq = 480
    mf = mido.MidiFile(type=1, ticks_per_beat=ppq)
    conductor = mido.MidiTrack()
    conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    conductor.append(mido.MetaMessage("marker", text="Section A", time=0))
    conductor.append(
        mido.MetaMessage("time_signature", numerator=3, denominator=4, time=ppq * 4 * 4)
    )
    mf.tracks.append(conductor)
    data = mido.MidiTrack()
    data.append(mido.MetaMessage("track_name", name="Lead", time=0))
    data.append(mido.Message("note_on", note=60, velocity=100, time=0))
    data.append(mido.Message("note_off", note=60, velocity=0, time=ppq * 4 * 4 + ppq * 3 * 4))
    mf.tracks.append(data)
    mf.save(path)
    return path


@pytest.fixture
def sustained_note_across_boundary(tmp_path: Path) -> Path:
    """Note-on in section A that runs past the boundary — should clamp in A."""
    ppq = 480
    bar = ppq * 4
    events: TrackEvents = [
        (0, mido.Message("note_on", note=60, velocity=100)),
        # note-off well past section A (which ends at 4*bar)
        (6 * bar, mido.Message("note_off", note=60, velocity=0)),
        # ensure the file extends long enough for section B to have content
        (8 * bar - ppq, mido.Message("note_on", note=64, velocity=100)),
        (8 * bar, mido.Message("note_off", note=64, velocity=0)),
    ]
    return make_midi(
        tmp_path / "sustain.mid",
        tracks=[events],
        markers=[(0, "A"), (4 * bar, "B")],
        track_names=["Lead"],
        ppq=ppq,
    )
