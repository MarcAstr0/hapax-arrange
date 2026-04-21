from __future__ import annotations

import mido

from hapax_arrange.model import SectionSpan, SourceTrack
from hapax_arrange.slicer import slice_all
from hapax_arrange.timing import TSChange

PPQ = 480
BAR = PPQ * 4


def _track(events: list[tuple[int, mido.Message | mido.MetaMessage]]) -> SourceTrack:
    return SourceTrack(index=0, name="T0", events=events)


def test_shift_to_zero() -> None:
    # A note-on at bar 2 in a section spanning [bar 1, bar 3) should land at bar 1 (rel).
    events = [
        (2 * BAR, mido.Message("note_on", note=60, velocity=100)),
        (2 * BAR + PPQ, mido.Message("note_off", note=60, velocity=0)),
    ]
    span = SectionSpan(name="A", start_tick=1 * BAR, end_tick=3 * BAR)
    [pc] = slice_all([_track(events)], [span], PPQ, [])
    assert pc.length_ticks == 2 * BAR
    on = [(t, m) for t, m in pc.events if not m.is_meta and m.type == "note_on"]
    assert on[0][0] == BAR


def test_length_preserves_trailing_silence() -> None:
    # Section is 4 bars long but the last event is at bar 1 — length_ticks must still be 4 bars.
    events = [
        (0, mido.Message("note_on", note=60, velocity=100)),
        (PPQ, mido.Message("note_off", note=60, velocity=0)),
    ]
    span = SectionSpan(name="A", start_tick=0, end_tick=4 * BAR)
    [pc] = slice_all([_track(events)], [span], PPQ, [])
    assert pc.length_ticks == 4 * BAR


def test_clamp_at_section_boundary() -> None:
    # Note-on mid-section with note-off after the section ends → clamp to end-1.
    events = [
        (0 * BAR, mido.Message("note_on", note=60, velocity=100)),
        (10 * BAR, mido.Message("note_off", note=60, velocity=0)),  # past end
    ]
    span = SectionSpan(name="A", start_tick=0, end_tick=4 * BAR)
    [pc] = slice_all([_track(events)], [span], PPQ, [])
    offs = [(t, m) for t, m in pc.events if not m.is_meta and m.type == "note_off"]
    assert len(offs) == 1
    assert offs[0][0] == 4 * BAR - 1
    assert pc.clamped_notes == 1


def test_stray_note_off_dropped() -> None:
    # Note-on in section A, its note-off falls inside section B — B sees a stray off.
    events = [
        (0, mido.Message("note_on", note=60, velocity=100)),
        (3 * BAR, mido.Message("note_off", note=60, velocity=0)),
    ]
    span_b = SectionSpan(name="B", start_tick=2 * BAR, end_tick=4 * BAR)
    [pc] = slice_all([_track(events)], [span_b], PPQ, [])
    offs = [(t, m) for t, m in pc.events if not m.is_meta and m.type == "note_off"]
    # The stray off is dropped, not copied into B.
    assert len(offs) == 0
    assert pc.stray_note_offs == 1


def test_meta_tempo_ts_stripped() -> None:
    events = [
        (0, mido.MetaMessage("set_tempo", tempo=500000)),
        (0, mido.MetaMessage("time_signature", numerator=4, denominator=4)),
        (0, mido.Message("note_on", note=60, velocity=100)),
        (PPQ, mido.Message("note_off", note=60, velocity=0)),
    ]
    span = SectionSpan(name="A", start_tick=0, end_tick=BAR)
    [pc] = slice_all([_track(events)], [span], PPQ, [])
    types = {m.type for _, m in pc.events}
    assert "set_tempo" not in types
    assert "time_signature" not in types


def test_ts_spanning_section_bars() -> None:
    # 4 bars of 4/4 (= 4 bars), then 4 bars of 2/4 (= 2 bars of 4/4 ticks but 4 bars of 2/4)
    # Span covers all 8 bars of ticks at 4/4 scale (32 beats of ticks).
    # With ts changes at tick 4*BAR switching to 2/4 (numerator=2 denominator=4):
    # bar width at 4/4 = 4*PPQ; bar width at 2/4 = 2*PPQ
    # Spans [0, 4*BAR + 4*(2*PPQ)) = [0, 4*BAR + 8*PPQ) covers 4 bars of 4/4 + 4 bars of 2/4
    ts_changes = [TSChange(0, 4, 4), TSChange(4 * BAR, 2, 4)]
    section_end = 4 * BAR + 4 * (2 * PPQ)
    span = SectionSpan(name="Mixed", start_tick=0, end_tick=section_end)
    [pc] = slice_all([_track([])], [span], PPQ, ts_changes)
    # 4 bars at 4/4 + 4 bars at 2/4 = 8 bars total in bar-count terms.
    assert abs(pc.length_bars - 8.0) < 0.001


def test_markers_stripped() -> None:
    events = [
        (0, mido.MetaMessage("marker", text="Intro")),
        (0, mido.Message("note_on", note=60, velocity=100)),
        (PPQ, mido.Message("note_off", note=60, velocity=0)),
    ]
    span = SectionSpan(name="A", start_tick=0, end_tick=BAR)
    [pc] = slice_all([_track(events)], [span], PPQ, [])
    for _, m in pc.events:
        assert not (m.is_meta and m.type == "marker")
