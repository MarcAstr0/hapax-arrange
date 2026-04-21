# CLAUDE.md

Project-specific guidance for Claude Code sessions. Read this first when resuming
work on `hapax-arrange`.

## What this is

A Python 3.11+ CLI that converts a DAW-exported multi-track MIDI file (with
section markers) into a Squarp Hapax import bundle: per-pattern `.mid` files
plus a human-readable `ARRANGEMENT.md` checklist. See `README.md` for the
user-facing overview.

## Dev loop

```bash
uv sync                     # install into .venv/
uv run pytest -q            # unit + CLI + demo regeneration; expect 63+ green
uv run ruff check           # lint; must pass clean before commit
uv run ruff format          # auto-format
uv run hapax-arrange --help # exercise the CLI
```

Quick end-to-end smoke against the checked-in demo:

```bash
rm -rf /tmp/h && uv run hapax-arrange examples/demo_song/input.mid -o /tmp/h
```

Expect 6 `.mid` files and `ARRANGEMENT.md` with "Unique patterns after dedup:
6 (from 12)" and no warnings.

## Architecture

```
cli.py → reader.parse → segmenter.segment → slicer.slice_all
       → dedup.assign_slots → Arrangement.build → validator.check
       → writer.write (unless --dry-run) → report.render
```

Each stage lives in its own module under `src/hapax_arrange/`. Pure stages
(segmenter, slicer, dedup, validator, report) are unit-tested without
touching the filesystem.

Dataclasses: `ParsedMidi`, `SectionSpan`, `PatternContent`, `PatternSlot`,
`Section`, `TrackMap`, `Arrangement` — all defined in `model.py`. `timing.py`
owns tick-to-bar conversion and is time-signature-aware (piecewise over
`TSChange` segments).

## Non-obvious invariants

These are easy to accidentally break. See `.claude/rules/midi-invariants.md`
for the full list; the load-bearing ones are:

1. **Note-offs use `(start, end]`**, everything else `[start, end)`. A note
   ending exactly at a section boundary closes in this section, not the
   next. Without this you get spurious "clamped" warnings on every boundary.
2. **Writer emits `end_of_track` with delta = `length_ticks - last_abs`**.
   This preserves trailing silence — a section ending quiet must stay its
   declared length, not get trimmed to the last note.
3. **MIDI track names must be latin-1 safe.** MIDI spec charset is latin-1.
   Em-dashes and other non-latin-1 chars crash `mf.save()`. The writer runs
   `raw.encode("latin-1", errors="replace").decode("latin-1")`.

## Testing conventions

- Fixtures are **synthesized in `tests/conftest.py`** via the `make_midi`
  helper. Don't check in `.mid` binaries (except `examples/demo_song/input.mid`,
  the canonical example).
- Each pipeline module has its own `test_<module>.py`. End-to-end CLI tests
  live in `test_cli.py`. The demo regeneration test in `test_demo_song.py`
  is a structural check, not a byte-for-byte diff.
- CLI tests use `click.testing.CliRunner()`. Click 8.3+ merges stderr into
  `result.output`; no `mix_stderr=False` kwarg.

## Packaging

- `uv init --package` layout: src/hapax_arrange/ with entry point
  `hapax_arrange.cli:main` in `pyproject.toml`'s `[project.scripts]`.
- Ruff config: line-length 100, target-version py311, lints E/F/I/UP/B/SIM.
- `uv.lock` is committed; `.venv/` is ignored.
- Install as a user command: `uv tool install .` or
  `uv tool install git+https://github.com/MarcAstr0/hapax-arrange`.

## Git conventions

- Default branch is `main`, tracks `origin/main` on GitHub.
- When Claude Code assists on a commit, credit it via the standard
  `Co-Authored-By:` footer (see `git log` for format).

## Hardware validation status

MVP has been validated only against synthesized fixtures and the programmatic
demo. End-to-end hardware validation (copy `MIDI/` to the Hapax SD card and
walk the checklist on a real song) is the remaining known-unknown — it
requires access to a Squarp Hapax + a DAW. Do not claim hardware-verified
in docs until that happens.
