from __future__ import annotations

from pathlib import Path

import mido
import pytest

from hapax_arrange.model import (
    Arrangement,
    PatternContent,
    PatternSlot,
    Section,
    TrackMap,
)
from hapax_arrange.writer import DRUM_LANE_LABELS, write

PPQ = 480
BAR = PPQ * 4


def _make_arrangement(slots: dict[int, list[PatternSlot]], tracks: list[TrackMap]) -> Arrangement:
    return Arrangement(
        ppq=PPQ,
        time_signature=(4, 4),
        tempo_bpm=120.0,
        song_name="test",
        input_path="test.mid",
        tracks=tracks,
        sections=[Section(name="A", track_to_slot={1: 1}, duration_bars=4.0)],
        pattern_slots=slots,
    )


def _pc(events: tuple, length_ticks: int = 4 * BAR, track_id: int = 0) -> PatternContent:
    return PatternContent(
        track_id=track_id,
        track_name="Lead",
        section_name="A",
        events=events,
        length_ticks=length_ticks,
        length_bars=length_ticks / BAR,
    )


def _slot(content: PatternContent, slot_index: int = 1, hapax_track: int = 1) -> PatternSlot:
    return PatternSlot(
        track_id=content.track_id,
        hapax_track=hapax_track,
        slot_index=slot_index,
        content_hash="abcd",
        length_bars=content.length_bars,
        length_ticks=content.length_ticks,
        sections_using=(content.section_name,),
        source_content=content,
    )


def test_roundtrip_type0_and_length_preserved(tmp_path: Path) -> None:
    content = _pc(
        events=(
            (0, mido.Message("note_on", note=60, velocity=100)),
            (PPQ, mido.Message("note_off", note=60, velocity=0)),
        ),
        length_ticks=4 * BAR,
    )
    slot = _slot(content)
    arr = _make_arrangement(
        {1: [slot]},
        [TrackMap(hapax_track=1, source_track=0, name="Lead", kind="poly")],
    )
    paths = write(arr, tmp_path / "out")
    assert len(paths) == 1

    mf = mido.MidiFile(paths[0])
    assert mf.type == 0
    assert mf.ticks_per_beat == PPQ
    # Total tick length of the emitted track = sum of deltas.
    total = sum(m.time for m in mf.tracks[0])
    assert total == 4 * BAR


def test_filename_convention(tmp_path: Path) -> None:
    content = _pc(events=((0, mido.Message("note_on", note=60, velocity=100)),))
    content = PatternContent(**{**content.__dict__, "section_name": "Verse Chorus!"})
    slot = PatternSlot(
        track_id=0,
        hapax_track=2,
        slot_index=3,
        content_hash="x",
        length_bars=4,
        length_ticks=4 * BAR,
        sections_using=("Verse Chorus!",),
        source_content=content,
    )
    arr = _make_arrangement(
        {2: [slot]},
        [TrackMap(hapax_track=2, source_track=0, name="Lead", kind="poly")],
    )
    [path] = write(arr, tmp_path / "out")
    assert path.name == "T02_P03_Verse_Chorus.mid"


def test_drum_track_name_injects_lane_labels(tmp_path: Path) -> None:
    content = _pc(
        events=(
            (0, mido.Message("note_on", channel=9, note=36, velocity=100)),
            (PPQ, mido.Message("note_off", channel=9, note=36, velocity=0)),
        ),
    )
    slot = _slot(content)
    arr = _make_arrangement(
        {1: [slot]},
        [TrackMap(hapax_track=1, source_track=0, name="Drums", kind="drum")],
    )
    [path] = write(arr, tmp_path / "out")
    mf = mido.MidiFile(path)
    names = [m.name for m in mf.tracks[0] if m.is_meta and m.type == "track_name"]
    assert names[0] == DRUM_LANE_LABELS


def test_force_overwrites_non_empty_dir(tmp_path: Path) -> None:
    outdir = tmp_path / "out"
    (outdir / "MIDI").mkdir(parents=True)
    (outdir / "MIDI" / "leftover.mid").write_bytes(b"junk")
    content = _pc(events=((0, mido.Message("note_on", note=60, velocity=100)),))
    slot = _slot(content)
    arr = _make_arrangement(
        {1: [slot]},
        [TrackMap(hapax_track=1, source_track=0, name="Lead", kind="poly")],
    )
    with pytest.raises(FileExistsError):
        write(arr, outdir)
    paths = write(arr, outdir, force=True)
    assert len(paths) == 1
    assert not (outdir / "MIDI" / "leftover.mid").exists()


def test_head_meta_emitted(tmp_path: Path) -> None:
    content = _pc(events=((0, mido.Message("note_on", note=60, velocity=100)),))
    slot = _slot(content)
    arr = _make_arrangement(
        {1: [slot]},
        [TrackMap(hapax_track=1, source_track=0, name="Lead", kind="poly")],
    )
    [path] = write(arr, tmp_path / "out")
    mf = mido.MidiFile(path)
    types = [m.type for m in mf.tracks[0] if m.is_meta]
    assert "track_name" in types
    assert "time_signature" in types
    assert "set_tempo" in types
    assert types[-1] == "end_of_track"
