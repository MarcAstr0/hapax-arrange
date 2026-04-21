# No binary test fixtures

Test fixtures live in `tests/conftest.py` and are **synthesized at runtime**
via the `make_midi()` helper. Do not check in new `.mid` files under
`tests/fixtures/` or equivalent.

**Exception**: `examples/demo_song/input.mid` is the one intentionally-
tracked binary. It's the canonical example for the README and for
`test_demo_song.py`, regenerated deterministically by
`examples/demo_song/build_input.py`.

**Why**: binary `.mid` files are opaque in diffs — reviewers can't see what
a fixture asserts. Keeping the fixture definitions in Python makes test
intent visible and version-controllable. A dedup test that relies on
"identical verses" is self-documenting when the Python says so; it's
invisible when hidden in bytes.

**How to apply**: when adding a new test case, extend `conftest.py` with
another fixture function that builds the `MidiFile` programmatically.
Follow the pattern of `verse_chorus_verse_chorus` or
`drums_with_lane_names`.

If you genuinely need a checked-in binary (e.g. a real-world DAW export
reported as miscompiling), put it under `tests/fixtures/real/` and document
its provenance in a sibling `README.md`. Ask Mario first.
