from __future__ import annotations

import pytest

from hapax_arrange.errors import NoMarkersError
from hapax_arrange.model import Marker
from hapax_arrange.segmenter import segment


def test_basic_sections() -> None:
    markers = [Marker(0, "Intro"), Marker(100, "Verse"), Marker(200, "Chorus")]
    spans = segment(markers, 300)
    assert [s.name for s in spans] == ["Intro", "Verse", "Chorus"]
    assert [(s.start_tick, s.end_tick) for s in spans] == [(0, 100), (100, 200), (200, 300)]


def test_implicit_start() -> None:
    # No marker at tick 0 → prepend "Section 1"
    markers = [Marker(50, "Verse"), Marker(150, "Chorus")]
    spans = segment(markers, 250)
    assert [s.name for s in spans] == ["Section 1", "Verse", "Chorus"]
    assert spans[0].start_tick == 0
    assert spans[0].end_tick == 50


def test_duplicate_names_renamed_only_on_collision() -> None:
    markers = [
        Marker(0, "Intro"),
        Marker(100, "Verse"),
        Marker(200, "Chorus"),
        Marker(300, "Verse"),
    ]
    spans = segment(markers, 400)
    names = [s.name for s in spans]
    assert names == ["Intro", "Verse 1", "Chorus", "Verse 2"]


def test_unique_name_not_renamed() -> None:
    markers = [Marker(0, "Intro"), Marker(100, "Verse")]
    spans = segment(markers, 200)
    assert [s.name for s in spans] == ["Intro", "Verse"]


def test_no_markers_raises() -> None:
    with pytest.raises(NoMarkersError):
        segment([], 1000)


def test_markers_past_end_raise() -> None:
    with pytest.raises(NoMarkersError):
        segment([Marker(5000, "late")], 1000)


def test_same_tick_markers_collapsed() -> None:
    markers = [Marker(0, "Intro"), Marker(0, "Start")]
    spans = segment(markers, 100)
    assert len(spans) == 1
    assert spans[0].name == "Intro"
