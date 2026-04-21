from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from hapax_arrange.cli import main


def _run(args: list[str]) -> tuple[int, str, str]:
    runner = CliRunner()
    result = runner.invoke(main, args, catch_exceptions=False)
    # Click 8.3 merges stderr into output; we search the merged text for both streams.
    merged = result.output
    return result.exit_code, merged, merged


def test_happy_path_emits_files_and_report(simple_intro_verse_chorus: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    code, _stdout, _stderr = _run([str(simple_intro_verse_chorus), "-o", str(out)])
    assert code == 0
    assert (out / "ARRANGEMENT.md").exists()
    files = sorted(p.name for p in (out / "MIDI").iterdir())
    assert len(files) == 3
    assert all(name.startswith("T01_") for name in files)


def test_dedup_collapses_verses(verse_chorus_verse_chorus: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    code, _stdout, _ = _run([str(verse_chorus_verse_chorus), "-o", str(out)])
    assert code == 0
    files = sorted((out / "MIDI").iterdir())
    # 2 unique patterns expected after dedup (Verse + Chorus)
    assert len(files) == 2


def test_no_dedup_gives_four_patterns(verse_chorus_verse_chorus: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    code, _stdout, _ = _run([str(verse_chorus_verse_chorus), "-o", str(out), "--no-dedup"])
    assert code == 0
    assert len(list((out / "MIDI").iterdir())) == 4


def test_no_markers_exits_1(no_markers_midi: Path, tmp_path: Path) -> None:
    code, _out, err = _run([str(no_markers_midi), "-o", str(tmp_path / "out")])
    assert code == 1
    assert "marker" in err.lower()


def test_type2_exits_2(type2_midi: Path, tmp_path: Path) -> None:
    code, _out, err = _run([str(type2_midi), "-o", str(tmp_path / "out")])
    assert code == 2
    assert "Type 2" in err


def test_existing_non_empty_output_exits_3(simple_intro_verse_chorus: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    (out / "MIDI").mkdir(parents=True)
    (out / "MIDI" / "placeholder.mid").write_bytes(b"stuff")
    code, _stdout, err = _run([str(simple_intro_verse_chorus), "-o", str(out)])
    assert code == 3
    assert "not empty" in err


def test_force_overwrites_output(simple_intro_verse_chorus: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    (out / "MIDI").mkdir(parents=True)
    (out / "MIDI" / "leftover.mid").write_bytes(b"stuff")
    code, _stdout, _ = _run([str(simple_intro_verse_chorus), "-o", str(out), "--force"])
    assert code == 0
    assert not (out / "MIDI" / "leftover.mid").exists()


def test_dry_run_emits_report_only(simple_intro_verse_chorus: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    code, _stdout, _ = _run([str(simple_intro_verse_chorus), "-o", str(out), "--dry-run"])
    assert code == 0
    assert (out / "ARRANGEMENT.md").exists()
    assert not (out / "MIDI").exists()


def test_long_section_warns_but_succeeds(long_section_over_32_bars: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    code, _stdout, err = _run([str(long_section_over_32_bars), "-o", str(out)])
    assert code == 0
    assert "truncate" in err
    md = (out / "ARRANGEMENT.md").read_text()
    assert "36.00 bars" in md or "36 bars" in md


def test_drum_flag_injects_lane_labels(drums_with_lane_names: Path, tmp_path: Path) -> None:
    import mido

    out = tmp_path / "out"
    # The drum track ends up at source index 1 (conductor is index 0)
    code, _stdout, _ = _run([str(drums_with_lane_names), "-o", str(out), "--drums", "1"])
    assert code == 0
    drum_file = next((out / "MIDI").iterdir())
    mf = mido.MidiFile(drum_file)
    track_name = next(m.name for m in mf.tracks[0] if m.is_meta and m.type == "track_name")
    assert "KICK" in track_name
    assert "SNARE" in track_name


def test_tempo_change_warns(tempo_change_midfile: Path, tmp_path: Path) -> None:
    code, _stdout, err = _run([str(tempo_change_midfile), "-o", str(tmp_path / "out")])
    assert code == 0
    assert "Tempo" in err


def test_ts_change_warns(ts_change_midfile: Path, tmp_path: Path) -> None:
    code, _stdout, err = _run([str(ts_change_midfile), "-o", str(tmp_path / "out")])
    assert code == 0
    assert "Time signature" in err


def test_sustained_note_clamped(sustained_note_across_boundary: Path, tmp_path: Path) -> None:
    code, _stdout, err = _run([str(sustained_note_across_boundary), "-o", str(tmp_path / "out")])
    assert code == 0
    assert "clamped" in err


@pytest.mark.parametrize("flag", ["--version", "--help"])
def test_standard_flags(flag: str) -> None:
    runner = CliRunner()
    result = runner.invoke(main, [flag])
    assert result.exit_code == 0
    assert result.output
