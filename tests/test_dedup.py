from __future__ import annotations

import mido

from hapax_arrange.dedup import assign_slots
from hapax_arrange.model import PatternContent

PPQ = 480


def _content(
    section: str,
    events: list[tuple[int, mido.Message]],
    length_ticks: int = PPQ * 16,
    track_id: int = 0,
) -> PatternContent:
    return PatternContent(
        track_id=track_id,
        track_name=f"T{track_id}",
        section_name=section,
        events=tuple(events),
        length_ticks=length_ticks,
        length_bars=length_ticks / (PPQ * 4),
    )


def _phrase(pitches: list[int]) -> list[tuple[int, mido.Message]]:
    events = []
    for i, p in enumerate(pitches):
        events.append((i * PPQ, mido.Message("note_on", note=p, velocity=100)))
        events.append((i * PPQ + PPQ // 2, mido.Message("note_off", note=p, velocity=0)))
    return events


def test_identical_content_collapses_to_one_slot() -> None:
    verse = _phrase([60, 62, 64])
    contents = [
        _content("Verse 1", verse),
        _content("Chorus", _phrase([67, 69, 71])),
        _content("Verse 2", verse),
    ]
    slots_per_track, section_slot_map = assign_slots(contents, ppq=PPQ)
    assert list(slots_per_track.keys()) == [1]
    slots = slots_per_track[1]
    assert len(slots) == 2
    # Verse slot is first-seen → slot 1; Chorus → slot 2
    assert slots[0].slot_index == 1
    assert set(slots[0].sections_using) == {"Verse 1", "Verse 2"}
    assert slots[1].slot_index == 2
    assert section_slot_map["Verse 1"][1] == 1
    assert section_slot_map["Verse 2"][1] == 1
    assert section_slot_map["Chorus"][1] == 2


def test_microtiming_jitter_absorbed_by_quantize() -> None:
    clean = _phrase([60, 62])
    # Jitter each event by 1-2 ticks — within the ppq/96 = 5-tick quantum.
    jittered = [(t + ((i % 3) - 1) * 2, m) for i, (t, m) in enumerate(clean)]
    contents = [_content("V1", clean), _content("V2", jittered)]
    slots_per_track, _ = assign_slots(contents, ppq=PPQ)
    assert len(slots_per_track[1]) == 1


def test_no_dedup_gives_one_slot_per_content() -> None:
    verse = _phrase([60, 62])
    contents = [_content("V1", verse), _content("V2", verse), _content("V3", verse)]
    slots_per_track, _ = assign_slots(contents, ppq=PPQ, enabled=False)
    assert len(slots_per_track[1]) == 3


def test_empty_section_does_not_consume_slot() -> None:
    contents = [
        _content("Intro", _phrase([60])),
        _content("Silent", []),
        _content("Outro", _phrase([62])),
    ]
    slots_per_track, section_slot_map = assign_slots(contents, ppq=PPQ)
    assert len(slots_per_track[1]) == 2
    assert "Silent" in section_slot_map
    assert 1 not in section_slot_map["Silent"]  # inactive


def test_first_appearance_order_determines_slot_index() -> None:
    a = _phrase([60])
    b = _phrase([70])
    contents = [_content("S1", a), _content("S2", b), _content("S3", a), _content("S4", b)]
    slots_per_track, _ = assign_slots(contents, ppq=PPQ)
    slots = slots_per_track[1]
    # First unique → slot 1 (the a-phrase), second → slot 2
    assert slots[0].slot_index == 1
    assert slots[0].sections_using == ("S1", "S3")
    assert slots[1].slot_index == 2
    assert slots[1].sections_using == ("S2", "S4")


def test_hapax_track_mapping() -> None:
    contents = [
        _content("Intro", _phrase([60]), track_id=0),
        _content("Intro", _phrase([70]), track_id=1),
    ]
    slots_per_track, section_slot_map = assign_slots(contents, ppq=PPQ, hapax_track_of={0: 1, 1: 2})
    assert set(slots_per_track.keys()) == {1, 2}
    assert section_slot_map["Intro"] == {1: 1, 2: 1}
