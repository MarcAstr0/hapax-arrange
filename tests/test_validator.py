from __future__ import annotations

import mido

from hapax_arrange.model import (
    Arrangement,
    ParsedMidi,
    PatternContent,
    PatternSlot,
    Section,
    SourceTrack,
    TrackMap,
)
from hapax_arrange.timing import TSChange
from hapax_arrange.validator import check

PPQ = 480
BAR = PPQ * 4


def _parsed(
    ts_changes: list[TSChange] | None = None,
    tempo_events: list[int] | None = None,
    ts: tuple[int, int] = (4, 4),
    tracks: list[SourceTrack] | None = None,
) -> ParsedMidi:
    return ParsedMidi(
        ppq=PPQ,
        initial_tempo_bpm=120.0,
        initial_time_signature=ts,
        ts_changes=ts_changes or [],
        tempo_events_after_zero=tempo_events or [],
        tracks=tracks or [],
        markers=[],
        total_length_ticks=4 * BAR,
        midi_type=1,
    )


def _arr(
    slots: dict[int, list[PatternSlot]] | None = None,
    tracks: list[TrackMap] | None = None,
) -> Arrangement:
    slots = slots or {1: []}
    tracks = tracks or [TrackMap(hapax_track=1, source_track=0, name="T0", kind="poly")]
    sections: list[Section] = []
    return Arrangement(
        ppq=PPQ,
        time_signature=(4, 4),
        tempo_bpm=120.0,
        song_name="x",
        input_path="x.mid",
        tracks=tracks,
        sections=sections,
        pattern_slots=slots,
    )


def _slot(length_bars: float, slot_index: int = 1, hapax_track: int = 1) -> PatternSlot:
    pc = PatternContent(
        track_id=0,
        track_name="T0",
        section_name="A",
        events=(),
        length_ticks=int(length_bars * BAR),
        length_bars=length_bars,
    )
    return PatternSlot(
        track_id=0,
        hapax_track=hapax_track,
        slot_index=slot_index,
        content_hash="",
        length_bars=length_bars,
        length_ticks=int(length_bars * BAR),
        sections_using=("A",),
        source_content=pc,
    )


def test_pattern_over_max_bars_warns() -> None:
    arr = _arr(slots={1: [_slot(40.0)]})
    warnings, errors = check(arr, _parsed(), [])
    assert errors == []
    assert any("40.00" in w or "truncate" in w for w in warnings)


def test_too_many_unique_per_track_errors() -> None:
    slots = [_slot(4.0, slot_index=i + 1) for i in range(17)]
    arr = _arr(slots={1: slots})
    _, errors = check(arr, _parsed(), [])
    assert any("unique patterns" in e for e in errors)


def test_too_many_tracks_errors() -> None:
    tracks = [
        TrackMap(hapax_track=i + 1, source_track=i, name=f"T{i}", kind="poly") for i in range(17)
    ]
    arr = _arr(slots={i + 1: [] for i in range(17)}, tracks=tracks)
    _, errors = check(arr, _parsed(), [])
    assert any("Track count" in e for e in errors)


def test_tempo_events_after_zero_warn() -> None:
    arr = _arr()
    warnings, _ = check(arr, _parsed(tempo_events=[480, 960]), [])
    assert any("Tempo" in w for w in warnings)


def test_ts_changes_warn() -> None:
    arr = _arr()
    warnings, _ = check(arr, _parsed(ts_changes=[TSChange(0, 4, 4), TSChange(BAR, 3, 4)]), [])
    assert any("Time signature changes" in w for w in warnings)


def test_mpe_heuristic_warn() -> None:
    # 4 channels in use
    events = []
    for ch in range(4):
        events.append((0, mido.Message("note_on", channel=ch, note=60, velocity=100)))
        events.append((PPQ, mido.Message("note_off", channel=ch, note=60, velocity=0)))
    src = SourceTrack(index=0, name="MPE", events=events)
    arr = _arr()
    warnings, _ = check(arr, _parsed(tracks=[src]), [src])
    assert any("MIDI channels" in w for w in warnings)


def test_drum_heuristic_warn() -> None:
    events = [
        (0, mido.Message("note_on", channel=9, note=36, velocity=100)),
        (PPQ, mido.Message("note_off", channel=9, note=36, velocity=0)),
    ]
    src = SourceTrack(index=0, name="Drums", events=events)
    arr = _arr()
    warnings, _ = check(arr, _parsed(tracks=[src]), [src], drum_ids=set())
    assert any("channel 10" in w for w in warnings)


def test_drum_heuristic_silent_when_flagged() -> None:
    events = [
        (0, mido.Message("note_on", channel=9, note=36, velocity=100)),
        (PPQ, mido.Message("note_off", channel=9, note=36, velocity=0)),
    ]
    src = SourceTrack(index=0, name="Drums", events=events)
    arr = _arr(tracks=[TrackMap(hapax_track=1, source_track=0, name="Drums", kind="drum")])
    warnings, _ = check(arr, _parsed(tracks=[src]), [src], drum_ids={0})
    assert not any("channel 10" in w for w in warnings)


def test_zero_note_track_warn() -> None:
    src = SourceTrack(index=0, name="Silent", events=[])
    arr = _arr()
    warnings, _ = check(arr, _parsed(tracks=[src]), [src])
    assert any("no notes" in w for w in warnings)


def test_clamped_notes_reported() -> None:
    pc = PatternContent(
        track_id=0,
        track_name="T0",
        section_name="A",
        events=(),
        length_ticks=BAR,
        length_bars=1.0,
        clamped_notes=3,
    )
    slot = PatternSlot(
        track_id=0,
        hapax_track=1,
        slot_index=1,
        content_hash="",
        length_bars=1.0,
        length_ticks=BAR,
        sections_using=("A",),
        source_content=pc,
    )
    arr = _arr(slots={1: [slot]})
    warnings, _ = check(arr, _parsed(), [])
    assert any("clamped" in w for w in warnings)
