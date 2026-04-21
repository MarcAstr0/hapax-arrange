from __future__ import annotations

from hapax_arrange.model import (
    Arrangement,
    PatternContent,
    PatternSlot,
    Section,
    TrackMap,
)
from hapax_arrange.report import render_markdown

PPQ = 480
BAR = PPQ * 4


def _pc(name: str = "A") -> PatternContent:
    return PatternContent(
        track_id=0,
        track_name="Lead",
        section_name=name,
        events=(),
        length_ticks=BAR,
        length_bars=1.0,
    )


def _slot(name: str, slot_index: int = 1, hapax_track: int = 1) -> PatternSlot:
    return PatternSlot(
        track_id=0,
        hapax_track=hapax_track,
        slot_index=slot_index,
        content_hash="abc",
        length_bars=1.0,
        length_ticks=BAR,
        sections_using=(name,),
        source_content=_pc(name),
    )


def test_rendered_sections_contain_expected_headers() -> None:
    slot = _slot("Intro")
    arr = Arrangement(
        ppq=PPQ,
        time_signature=(4, 4),
        tempo_bpm=120.0,
        song_name="demo",
        input_path="demo.mid",
        tracks=[TrackMap(hapax_track=1, source_track=0, name="Lead", kind="poly")],
        sections=[Section(name="Intro", track_to_slot={1: 1}, duration_bars=4.0)],
        pattern_slots={1: [slot]},
    )
    md = render_markdown(arr)
    for header in [
        "# Hapax Import Plan: demo",
        "## Summary",
        "## Warnings",
        "## Track Map",
        "## Pattern Slots",
        "## Sections",
        "## Song Order",
        "## Import Checklist",
        "## Section Build",
        "## Song Build",
    ]:
        assert header in md
    assert "T01_P01_Intro.mid" in md
    assert "None." in md  # no warnings


def test_sections_matrix_shows_dash_for_inactive() -> None:
    slot1 = _slot("Intro", slot_index=1, hapax_track=1)
    arr = Arrangement(
        ppq=PPQ,
        time_signature=(4, 4),
        tempo_bpm=120.0,
        song_name="demo",
        input_path="demo.mid",
        tracks=[
            TrackMap(hapax_track=1, source_track=0, name="Lead", kind="poly"),
            TrackMap(hapax_track=2, source_track=1, name="Bass", kind="poly"),
        ],
        sections=[Section(name="Intro", track_to_slot={1: 1}, duration_bars=4.0)],
        pattern_slots={1: [slot1], 2: []},
    )
    md = render_markdown(arr)
    # Intro row should have P01 for T1 and — for T2
    assert "| Intro | P01 | — |" in md


def test_warnings_and_errors_rendered() -> None:
    slot = _slot("Intro")
    arr = Arrangement(
        ppq=PPQ,
        time_signature=(4, 4),
        tempo_bpm=120.0,
        song_name="demo",
        input_path="demo.mid",
        tracks=[TrackMap(hapax_track=1, source_track=0, name="Lead", kind="poly")],
        sections=[Section(name="Intro", track_to_slot={1: 1}, duration_bars=4.0)],
        pattern_slots={1: [slot]},
        warnings=["test warning"],
        errors=["test error"],
    )
    md = render_markdown(arr)
    assert "test warning" in md
    assert "**ERROR**: test error" in md
