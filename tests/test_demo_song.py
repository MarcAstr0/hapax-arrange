"""End-to-end check against the example in examples/demo_song/.

Regenerates the output and asserts structural properties rather than byte-for-byte
equality, so the test stays useful as the renderer evolves.
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from hapax_arrange.cli import main

DEMO_DIR = Path(__file__).resolve().parent.parent / "examples" / "demo_song"


def test_demo_song_regenerates(tmp_path: Path) -> None:
    input_mid = DEMO_DIR / "input.mid"
    assert input_mid.exists(), "examples/demo_song/input.mid missing — run build_input.py"

    out = tmp_path / "output"
    result = CliRunner().invoke(main, [str(input_mid), "-o", str(out)], catch_exceptions=False)
    assert result.exit_code == 0, result.output

    files = sorted(p.name for p in (out / "MIDI").iterdir())
    # 4 lead slots (Intro, Verse, Chorus, Outro after dedup) + 2 bass slots (Intro/Outro, V/C body)
    assert len(files) == 6, files

    md = (out / "ARRANGEMENT.md").read_text()
    assert "Unique patterns after dedup: 6 (from 12)" in md
    assert "Intro" in md and "Verse 1" in md and "Chorus 1" in md and "Outro" in md
    # No errors / clean input → Warnings section should say None.
    assert "\n## Warnings\nNone." in md
