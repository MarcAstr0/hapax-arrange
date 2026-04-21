# MIDI pipeline invariants

Three correctness rules that are easy to accidentally break when editing
`slicer.py` or `writer.py`. If you touch either, re-check all three.

## 1. Note-offs use `(start, end]`, everything else uses `[start, end)`

In `slicer._slice_one`, a `note_off` at `abs_tick == span.end_tick` belongs
to **this** section (it closes a note that started here), not the next one.
All other events use strict half-open `[start, end)`.

**Why**: DAWs commonly export notes that end exactly at section boundaries.
Under strict `[start, end)` the note-on is in the section, the note-off is
not, and the slicer emits a synthetic clamped note-off one tick early —
producing a spurious "clamped" warning on every well-formed input.

**How to apply**: if you add new event-type handling, put `note_off` on the
`(start, end]` path and everything else on `[start, end)`.

## 2. `writer.py` must emit `end_of_track` with delta = `length_ticks - last_abs`

In `writer._write_slot`, after all body events are appended, emit:

```python
track.append(mido.MetaMessage("end_of_track", time=max(0, slot.length_ticks - prev)))
```

**Why**: without an explicit `end_of_track` at the section length, `mido`
trims trailing silence to the last event. A section ending quiet (e.g. an
Outro with a single hit at bar 1 over a 4-bar span) would come back as a
1-bar pattern, corrupting the Hapax section duration.

**How to apply**: any writer refactor that changes event-emission structure
must preserve this trailer.

## 3. MIDI track names must be latin-1 encodable

The MIDI spec charset is latin-1. `mf.save()` crashes with
`UnicodeEncodeError` on characters outside that range — em-dash, curly
quotes, accented non-latin-1 chars, etc.

In `writer._track_name`:

```python
raw = f"{slot.source_content.track_name} - {slot.sections_using[0]}"
return raw.encode("latin-1", errors="replace").decode("latin-1")
```

Use an ASCII hyphen (`-`), never an em-dash (`—`), in the format string.

**Why**: this was a real bug caught by `test_writer.py`. The source track
name can contain any Unicode (DAWs are permissive); the emitted `track_name`
meta must be latin-1 safe.

**How to apply**: every string passed to `mido.MetaMessage("track_name", ...)`
should go through the latin-1 replace-and-decode dance, or be composed
entirely from already-sanitized ASCII.
