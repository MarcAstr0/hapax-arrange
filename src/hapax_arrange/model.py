"""Dataclasses for the hapax-arrange pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from hapax_arrange.timing import TSChange

if TYPE_CHECKING:
    import mido


@dataclass(frozen=True)
class Marker:
    tick: int
    name: str


@dataclass
class SourceTrack:
    """A parsed source track: ordered (abs_tick, message) pairs plus metadata."""

    index: int
    name: str
    events: list[tuple[int, mido.Message | mido.MetaMessage]]


@dataclass
class ParsedMidi:
    ppq: int
    initial_tempo_bpm: float
    initial_time_signature: tuple[int, int]
    ts_changes: list[TSChange]
    tempo_events_after_zero: list[int]  # ticks where extra tempo events appear
    tracks: list[SourceTrack]
    markers: list[Marker]
    total_length_ticks: int
    midi_type: int


@dataclass(frozen=True)
class SectionSpan:
    name: str
    start_tick: int
    end_tick: int  # exclusive


@dataclass(frozen=True)
class PatternContent:
    track_id: int
    track_name: str
    section_name: str
    events: tuple[tuple[int, mido.Message | mido.MetaMessage], ...]
    length_ticks: int
    length_bars: float
    clamped_notes: int = 0
    stray_note_offs: int = 0


@dataclass(frozen=True)
class PatternSlot:
    track_id: int  # source track index
    hapax_track: int  # 1..16
    slot_index: int  # 1..16
    content_hash: str
    length_bars: float
    length_ticks: int
    sections_using: tuple[str, ...]
    source_content: PatternContent


@dataclass
class Section:
    name: str
    track_to_slot: dict[int, int]  # hapax_track -> slot_index (1-based); missing = inactive
    duration_bars: float


@dataclass
class TrackMap:
    hapax_track: int  # 1..16
    source_track: int
    name: str
    kind: str  # "poly" | "drum"


@dataclass
class Arrangement:
    ppq: int
    time_signature: tuple[int, int]
    tempo_bpm: float
    song_name: str
    input_path: str
    tracks: list[TrackMap]
    sections: list[Section]
    pattern_slots: dict[int, list[PatternSlot]]  # hapax_track -> slots in slot_index order
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @classmethod
    def build(
        cls,
        parsed: ParsedMidi,
        spans: list[SectionSpan],
        contents: list[PatternContent],
        slots_per_track: dict[int, list[PatternSlot]],
        section_slot_map: dict[str, dict[int, int]],
        track_map: list[TrackMap],
        *,
        song_name: str,
        input_path: str,
    ) -> Arrangement:
        section_name_to_duration = {s.name: _span_duration_bars(s, parsed) for s in spans}
        sections = [
            Section(
                name=span.name,
                track_to_slot=section_slot_map.get(span.name, {}),
                duration_bars=section_name_to_duration[span.name],
            )
            for span in spans
        ]
        return cls(
            ppq=parsed.ppq,
            time_signature=parsed.initial_time_signature,
            tempo_bpm=parsed.initial_tempo_bpm,
            song_name=song_name,
            input_path=input_path,
            tracks=track_map,
            sections=sections,
            pattern_slots=slots_per_track,
        )


def _span_duration_bars(span: SectionSpan, parsed: ParsedMidi) -> float:
    from hapax_arrange.timing import ticks_to_bars

    return ticks_to_bars(
        span.start_tick,
        span.end_tick - span.start_tick,
        parsed.ppq,
        parsed.ts_changes,
    )
