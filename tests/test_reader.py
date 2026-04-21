from __future__ import annotations

from pathlib import Path

import mido
import pytest

from hapax_arrange.errors import UnsupportedMidiTypeError
from hapax_arrange.reader import parse
from tests.conftest import make_midi, notes


def test_parses_ppq_tempo_ts(simple_intro_verse_chorus: Path) -> None:
    parsed = parse(simple_intro_verse_chorus)
    assert parsed.ppq == 480
    assert parsed.initial_time_signature == (4, 4)
    assert abs(parsed.initial_tempo_bpm - 120.0) < 0.01


def test_parses_markers(simple_intro_verse_chorus: Path) -> None:
    parsed = parse(simple_intro_verse_chorus)
    names = [m.name for m in parsed.markers]
    assert names == ["Intro", "Verse", "Chorus"]
    ticks = [m.tick for m in parsed.markers]
    bar = 480 * 4
    assert ticks == [0, 8 * bar, 16 * bar]


def test_abs_tick_promotion(simple_intro_verse_chorus: Path) -> None:
    parsed = parse(simple_intro_verse_chorus)
    # Find the lead track (skip the conductor)
    lead = next(t for t in parsed.tracks if t.name == "Lead")
    note_ons = [(t, m) for t, m in lead.events if hasattr(m, "type") and m.type == "note_on"]
    # Notes were placed at 0, 8*bar, 16*bar, 23*bar
    bar = 480 * 4
    ticks = [t for t, _ in note_ons]
    assert ticks == [0, 8 * bar, 16 * bar, 23 * bar]


def test_total_length_tracks_latest_event(simple_intro_verse_chorus: Path) -> None:
    parsed = parse(simple_intro_verse_chorus)
    bar = 480 * 4
    # Last event is note_off of the final note at 23*bar + bar/4
    assert parsed.total_length_ticks == 23 * bar + bar // 4


def test_type2_rejected(type2_midi: Path) -> None:
    with pytest.raises(UnsupportedMidiTypeError):
        parse(type2_midi)


def test_missing_track_name_falls_back(tmp_path: Path) -> None:
    # Make a file without any track_name meta — should get "Track N" fallback
    path = tmp_path / "noname.mid"
    mf = mido.MidiFile(type=1, ticks_per_beat=480)
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(120)))
    track.append(mido.Message("note_on", note=60, velocity=100, time=0))
    track.append(mido.Message("note_off", note=60, velocity=0, time=480))
    mf.tracks.append(track)
    mf.save(path)
    parsed = parse(path)
    assert parsed.tracks[0].name == "Track 0"


def test_markers_from_any_track(tmp_path: Path) -> None:
    # Ableton-style: markers on a conductor track; our make_midi already does this.
    # Reaper-style: markers on track 0 alongside notes. Build one by hand.
    path = tmp_path / "reaper_style.mid"
    mf = mido.MidiFile(type=1, ticks_per_beat=480)
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(120), time=0))
    track.append(mido.MetaMessage("marker", text="Intro", time=0))
    track.append(mido.Message("note_on", note=60, velocity=100, time=0))
    track.append(mido.Message("note_off", note=60, velocity=0, time=480 * 4))
    track.append(mido.MetaMessage("marker", text="Verse", time=0))
    mf.tracks.append(track)
    mf.save(path)
    parsed = parse(path)
    assert [m.name for m in parsed.markers] == ["Intro", "Verse"]


def test_dedupes_markers_from_multiple_tracks(tmp_path: Path) -> None:
    # Marker appearing on both conductor track and data track should collapse to one
    path = make_midi(
        tmp_path / "dup.mid",
        tracks=[notes(0, 60, start=0, dur=480)],
        markers=[(0, "Intro")],
    )
    # Manually splice another "Intro" marker at tick 0 into the data track
    mf = mido.MidiFile(path)
    mf.tracks[1].insert(0, mido.MetaMessage("marker", text="Intro", time=0))
    mf.save(path)
    parsed = parse(path)
    intros = [m for m in parsed.markers if m.name == "Intro" and m.tick == 0]
    assert len(intros) == 1


def test_ts_changes_captured(tmp_path: Path) -> None:
    path = tmp_path / "ts_change.mid"
    mf = mido.MidiFile(type=1, ticks_per_beat=480)
    conductor = mido.MidiTrack()
    conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    conductor.append(
        mido.MetaMessage("time_signature", numerator=3, denominator=4, time=480 * 4 * 4)
    )
    mf.tracks.append(conductor)
    data = mido.MidiTrack()
    data.append(mido.Message("note_on", note=60, velocity=100, time=0))
    data.append(mido.Message("note_off", note=60, velocity=0, time=480))
    mf.tracks.append(data)
    mf.save(path)
    parsed = parse(path)
    assert len(parsed.ts_changes) == 2
    assert parsed.ts_changes[0].numerator == 4
    assert parsed.ts_changes[1].numerator == 3
    assert parsed.ts_changes[1].tick == 480 * 4 * 4
