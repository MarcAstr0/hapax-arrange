"""Build the demo input.mid deterministically.

Run with ``uv run python examples/demo_song/build_input.py``.
"""

from __future__ import annotations

from pathlib import Path

import mido

PPQ = 480
BAR = PPQ * 4

SECTIONS = [
    ("Intro", 4),
    ("Verse", 8),
    ("Chorus", 8),
    ("Verse", 8),
    ("Chorus", 8),
    ("Outro", 4),
]

TrackEvents = list[tuple[int, "mido.Message"]]


def _verse_phrase(channel: int, root: int) -> TrackEvents:
    events: TrackEvents = []
    pitches = [root, root + 3, root + 5, root + 7]
    for i, p in enumerate(pitches):
        events.append((i * PPQ, mido.Message("note_on", channel=channel, note=p, velocity=90)))
        events.append(
            (i * PPQ + PPQ // 2, mido.Message("note_off", channel=channel, note=p, velocity=0))
        )
    return events


def _chorus_phrase(channel: int, root: int) -> TrackEvents:
    events: TrackEvents = []
    pitches = [root + 7, root + 9, root + 12, root + 9, root + 7, root + 5, root + 3, root]
    for i, p in enumerate(pitches):
        events.append(
            (i * PPQ // 2, mido.Message("note_on", channel=channel, note=p, velocity=100))
        )
        events.append(
            (
                i * PPQ // 2 + PPQ // 4,
                mido.Message("note_off", channel=channel, note=p, velocity=0),
            )
        )
    return events


def _repeat(phrase: TrackEvents, span_bars: int) -> TrackEvents:
    out: TrackEvents = []
    for b in range(span_bars):
        offset = b * BAR
        for t, m in phrase:
            out.append((t + offset, m))
    return out


def _section_events(name: str, bars: int, channel: int) -> TrackEvents:
    if name == "Intro":
        phrase: TrackEvents = [
            (0, mido.Message("note_on", channel=channel, note=60, velocity=70)),
            (BAR, mido.Message("note_off", channel=channel, note=60, velocity=0)),
        ]
        return _repeat(phrase, bars)
    if name == "Verse":
        return _repeat(_verse_phrase(channel, 60), bars)
    if name == "Chorus":
        return _repeat(_chorus_phrase(channel, 60), bars // 2)  # chorus phrase is 2 bars
    if name == "Outro":
        phrase = [
            (0, mido.Message("note_on", channel=channel, note=60, velocity=50)),
            (BAR, mido.Message("note_off", channel=channel, note=60, velocity=0)),
        ]
        return _repeat(phrase, bars)
    raise ValueError(name)


def _append_delta_sorted(track: mido.MidiTrack, events: TrackEvents) -> None:
    events.sort(key=lambda e: (e[0], 0 if e[1].type == "note_off" else 1))
    prev = 0
    for t, m in events:
        track.append(m.copy(time=max(0, t - prev)))
        prev = t


def build(path: Path) -> None:
    mf = mido.MidiFile(type=1, ticks_per_beat=PPQ)

    # Conductor with tempo, TS, and markers — deltas driven by section durations.
    c = mido.MidiTrack()
    c.append(mido.MetaMessage("track_name", name="conductor", time=0))
    c.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(110), time=0))
    c.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    for i, (name, _) in enumerate(SECTIONS):
        delta = 0 if i == 0 else SECTIONS[i - 1][1] * BAR
        c.append(mido.MetaMessage("marker", text=name, time=delta))
    mf.tracks.append(c)

    # Data tracks: Lead + Bass
    lead_events: TrackEvents = []
    bass_events: TrackEvents = []
    pos = 0
    for name, bars in SECTIONS:
        for t_, m in _section_events(name, bars, channel=0):
            lead_events.append((pos + t_, m))
        bass_one_bar: TrackEvents = [
            (0, mido.Message("note_on", channel=1, note=36, velocity=100)),
            (BAR, mido.Message("note_off", channel=1, note=36, velocity=0)),
        ]
        for t_, m in _repeat(bass_one_bar, bars):
            bass_events.append((pos + t_, m))
        pos += bars * BAR

    for tname, events in [("Lead", lead_events), ("Bass", bass_events)]:
        tr = mido.MidiTrack()
        tr.append(mido.MetaMessage("track_name", name=tname, time=0))
        _append_delta_sorted(tr, events)
        mf.tracks.append(tr)

    path.parent.mkdir(parents=True, exist_ok=True)
    mf.save(path)


if __name__ == "__main__":
    out = Path(__file__).parent / "input.mid"
    build(out)
    print("wrote", out)
