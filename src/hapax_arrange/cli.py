"""click entry point for hapax-arrange."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from hapax_arrange import __version__
from hapax_arrange.dedup import assign_slots
from hapax_arrange.errors import (
    HapaxArrangeError,
    NoMarkersError,
    UnsupportedMidiTypeError,
)
from hapax_arrange.model import Arrangement, ParsedMidi, SourceTrack, TrackMap
from hapax_arrange.reader import parse
from hapax_arrange.report import render as render_report
from hapax_arrange.segmenter import segment
from hapax_arrange.slicer import slice_all
from hapax_arrange.validator import check as validate
from hapax_arrange.writer import write as write_midi


@click.command()
@click.argument("input_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "-o",
    "--output",
    "output_dir",
    default=Path("./hapax_import"),
    type=click.Path(file_okay=False, path_type=Path),
    show_default=True,
)
@click.option("--drums", "drums", default="", help="Source track indices marked as drum, e.g. 0,2")
@click.option("--no-dedup", is_flag=True, help="Disable pattern deduplication.")
@click.option("--max-bars", default=32, show_default=True, help="Pattern length cap in bars.")
@click.option("--dry-run", is_flag=True, help="Emit ARRANGEMENT.md only; skip .mid files.")
@click.option("--force", is_flag=True, help="Overwrite a non-empty output directory.")
@click.option("--name", default=None, help="Song name (default: input stem).")
@click.option("-v", "--verbose", is_flag=True, help="Print stage-by-stage progress.")
@click.option("--dump-sections", is_flag=True, help="Print SectionSpan list and exit.")
@click.option("--dump-slots", is_flag=True, help="Print slot plan and exit (skip writer/report).")
@click.version_option(__version__, prog_name="hapax-arrange")
def main(  # noqa: PLR0913
    input_path: Path,
    output_dir: Path,
    drums: str,
    no_dedup: bool,
    max_bars: int,
    dry_run: bool,
    force: bool,
    name: str | None,
    verbose: bool,
    dump_sections: bool,
    dump_slots: bool,
) -> None:
    """Convert a DAW-exported MIDI file into a Hapax-ready import bundle."""
    try:
        if verbose:
            click.echo(f"reading {input_path}", err=True)
        parsed = parse(input_path)
        if verbose:
            click.echo(
                f"parsed: ppq={parsed.ppq} tempo={parsed.initial_tempo_bpm:.1f} "
                f"ts={parsed.initial_time_signature} tracks={len(parsed.tracks)} "
                f"markers={len(parsed.markers)}",
                err=True,
            )

        spans = segment(parsed.markers, parsed.total_length_ticks)
        if verbose or dump_sections:
            click.echo(f"sections: {len(spans)}", err=True)
            for s in spans:
                click.echo(
                    f"  {s.name}: ticks {s.start_tick}-{s.end_tick} "
                    f"({s.end_tick - s.start_tick} ticks)",
                    err=True,
                )
        if dump_sections:
            return

        drum_ids = _parse_drum_ids(drums)
        data_tracks, track_map = _build_track_map(parsed, drum_ids)
        if verbose:
            for tm in track_map:
                click.echo(
                    f"  T{tm.hapax_track:02d} <- src#{tm.source_track} {tm.name} ({tm.kind})",
                    err=True,
                )

        if not data_tracks:
            click.echo("error: no source tracks carry notes", err=True)
            sys.exit(1)

        contents = slice_all(data_tracks, spans, parsed.ppq, parsed.ts_changes)
        hapax_of = {tm.source_track: tm.hapax_track for tm in track_map}
        slots_per_track, section_slot_map = assign_slots(
            contents, ppq=parsed.ppq, enabled=not no_dedup, hapax_track_of=hapax_of
        )

        # Print a summary
        total_unique = sum(len(s) for s in slots_per_track.values())
        total_raw = len([c for c in contents if any(not m.is_meta for _, m in c.events)])
        click.echo(f"unique patterns after dedup: {total_unique} (from {total_raw})")
        for hapax_track in sorted(slots_per_track.keys()):
            tm = next(t for t in track_map if t.hapax_track == hapax_track)
            click.echo(f"  T{hapax_track:02d} {tm.name}:")
            for slot in slots_per_track[hapax_track]:
                used = ", ".join(slot.sections_using)
                click.echo(
                    f"    P{slot.slot_index:02d} {slot.length_bars:.2f} bars — used in {used}"
                )

        if dump_slots:
            return

        song_name = name or input_path.stem
        arrangement = Arrangement.build(
            parsed,
            spans,
            contents,
            slots_per_track,
            section_slot_map,
            track_map,
            song_name=song_name,
            input_path=str(input_path),
        )

        warnings, errors = validate(
            arrangement, parsed, data_tracks, max_bars=max_bars, drum_ids=drum_ids
        )
        arrangement.warnings = warnings
        arrangement.errors = errors
        for w in warnings:
            click.echo(f"warning: {w}", err=True)
        for e in errors:
            click.echo(f"error: {e}", err=True)

        if errors:
            report_path = render_report(arrangement, output_dir)
            click.echo(f"wrote {report_path} (validation failed — review and fix)", err=True)
            sys.exit(1)

        if not dry_run:
            paths = write_midi(arrangement, output_dir, force=force)
            if verbose:
                for p in paths:
                    click.echo(f"  wrote {p}", err=True)
            click.echo(f"wrote {len(paths)} pattern file(s) to {output_dir / 'MIDI'}")

        report_path = render_report(arrangement, output_dir)
        click.echo(f"wrote {report_path}")

    except UnsupportedMidiTypeError as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(2)
    except NoMarkersError as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(1)
    except HapaxArrangeError as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(1)
    except FileExistsError as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(3)
    except OSError as e:
        click.echo(f"error: cannot read {input_path}: {e}", err=True)
        sys.exit(2)


def _parse_drum_ids(raw: str) -> set[int]:
    if not raw.strip():
        return set()
    return {int(x.strip()) for x in raw.split(",") if x.strip()}


def _build_track_map(
    parsed: ParsedMidi, drum_ids: set[int]
) -> tuple[list[SourceTrack], list[TrackMap]]:
    """Filter out no-note source tracks and assign Hapax track numbers 1..N."""
    data_tracks: list[SourceTrack] = []
    for t in parsed.tracks:
        if any(
            not m.is_meta and m.type in ("note_on", "note_off") and getattr(m, "velocity", 0) >= 0
            for _, m in t.events
        ):
            data_tracks.append(t)
    track_map: list[TrackMap] = []
    for i, t in enumerate(data_tracks):
        kind = "drum" if t.index in drum_ids else "poly"
        track_map.append(TrackMap(hapax_track=i + 1, source_track=t.index, name=t.name, kind=kind))
    return data_tracks, track_map


if __name__ == "__main__":
    main()
