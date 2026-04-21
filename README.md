# hapax-arrange

A CLI that turns a DAW-exported multi-track MIDI file (with section markers) into a
Squarp Hapax-ready import bundle: per-pattern `.mid` files plus a human-readable
`ARRANGEMENT.md` checklist that makes the on-device build mechanical.

```
song.mid (DAW)              hapax-arrange               Hapax SD card
  Intro                  ----------------->           MIDI/T01_P01_Intro.mid
  Verse                                               MIDI/T01_P02_Verse.mid
  Chorus                                              MIDI/T01_P03_Chorus.mid
  Verse   (== Verse)                                  MIDI/T02_P01_Intro.mid
  Chorus  (== Chorus)                                 ...
                                                      ARRANGEMENT.md
```

Identical sections collapse into one pattern slot (Verse × 4 → one import + four
section references). The checklist walks you through the Hapax import dialog and
the section/song build, step by step.

## What problem it solves

Hapax MIDI import is strictly **pattern-level**: one MIDI track → one pattern, ≤32
bars, overwrite. The arrangement — which section plays when, for how long, in what
order — has to be built on-device (see [Hapax manual §5 / §6.7][manual]). For a
song with 5 sections × 8 tracks that's 40 imports, each requiring you to pick the
right file into the right slot. `hapax-arrange` prepares everything so the import
is mechanical rather than creative.

[manual]: https://squarp.net/hapax/manual/

## Install

Requires Python 3.11+. Uses `uv` for development and packaging.

```bash
# install the tool as a user command
uv tool install git+https://github.com/MarcAstr0/hapax-arrange
# or from a local checkout
uv tool install .

# alternative via pipx
pipx install .
```

## Quick start

```bash
hapax-arrange my_song.mid -o ./hapax_import
```

Produces:

```
hapax_import/
├── ARRANGEMENT.md
└── MIDI/
    ├── T01_P01_Intro.mid
    ├── T01_P02_Verse.mid
    ├── ...
```

Copy `hapax_import/MIDI/` to your Hapax SD card under `/MIDI/` and follow the
checklist in `ARRANGEMENT.md`.

## CLI

| Flag | Default | Effect |
|---|---|---|
| `-o, --output DIR` | `./hapax_import` | Output root |
| `--drums T1,T2` | — | Mark source tracks as drum (injects Hapax lane labels) |
| `--no-dedup` | dedup on | Disable pattern deduplication |
| `--max-bars N` | 32 | Pattern length cap in bars |
| `--dry-run` | off | Emit `ARRANGEMENT.md` only; skip `.mid` files |
| `--force` | off | Overwrite a non-empty output directory |
| `--name NAME` | input stem | Song name used in the arrangement sheet |
| `-v, --verbose` | off | Print stage-by-stage progress |
| `--version` | | Print version and exit |

Exit codes: `0` success, `1` validation error (missing markers, >16 patterns,
>16 tracks), `2` unreadable / Type 2 input, `3` non-empty output dir without
`--force`.

## Requirements on the input MIDI

1. **Type 0 or Type 1.** Type 2 is rejected.
2. **Section markers required.** Add a marker at the start of every section
   (Intro, Verse, Chorus, Bridge, Outro, …). DAW recipes below.
3. **Tempo and time signature are read at tick 0.** Changes mid-file produce
   warnings and are not preserved in the per-pattern files (Hapax tempo is
   project-level).

### DAW recipes for adding markers

- **Ableton Live**: `Create → Insert Locator`, then rename the locator.
  `File → Export MIDI File` exports the clip with markers in the Type 1 file.
- **Reaper**: `Insert → Marker` on the timeline (shortcut `M`). `File → Render`
  → format `MIDI`.
- **Logic Pro**: show the Marker track, double-click to create, name the marker.
  `File → Export → Selection as MIDI File…`.
- **Bitwig Studio**: `Edit Menu → Insert Cue Marker`, rename. Export via
  `File → Export…` with MIDI format.

## What gets deduplicated

Patterns are collapsed when their *note/CC content* is identical (up to a small
quantization window that absorbs microtiming jitter). This means identical
Verses collapse into one slot even if the surrounding track mix differs — the
Hapax section layer handles that.

`--no-dedup` disables collapsing, useful when you want every section to live in
its own slot even if the content is identical.

## Limitations

- **Markers required.** No auto-segmentation in the MVP.
- **MPE is not supported.** Hapax cannot import MPE; tracks using >3 channels
  are flagged with a warning and written out without per-note channel data.
- **Tempo automation is dropped.** Hapax tempo is project-level.
- **Automation lanes**: CC and pitch-bend are preserved; program-change is not
  mapped to the Hapax per-pattern PC field (must be set on-device).
- **Single project.** The MVP doesn't split a long song across two Hapax
  projects (proA / proB); maximum 16 tracks × 16 patterns × 1 project.

## Development

```bash
uv sync                 # install deps into .venv/
uv run pytest           # run the test suite
uv run ruff check       # lint
uv run ruff format      # auto-format
uv run hapax-arrange --help
```

The test fixtures are synthesized programmatically in `tests/conftest.py` — no
binary `.mid` files checked into git apart from `examples/demo_song/input.mid`.

## References

- Hapax manual: <https://squarp.net/hapax/manual/>
- Squarp community forum: <https://squarp.community>
- `mido` docs: <https://mido.readthedocs.io/>

## License

MIT
