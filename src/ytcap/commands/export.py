"""Export command."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace

from ytcap.app.export_subtitles import (
    ExportSubtitlesOptions,
    ExportSubtitlesResult,
    export_subtitles,
)


def configure_parser(parser: ArgumentParser) -> None:
    parser.add_argument("--input", required=True, help="SRT/VTT file or directory")
    parser.add_argument("--segments", choices=("cue", "sentence"), default="cue", help="segment type")
    parser.add_argument("--format", choices=("jsonl",), default="jsonl", help="output format")
    parser.add_argument("--out", default="./data/normalized", help="output directory")
    parser.add_argument("--video-id", help="video ID override for a single file")
    parser.add_argument("--lang", help="language override")
    parser.add_argument("--category", help="dataset category value for exported JSONL records")
    parser.set_defaults(handler=handle)


def handle(args: Namespace) -> int:
    result = export_subtitles(_options_from_args(args))
    print("Export complete.")
    print(f"Input: {args.input}")
    print(f"Segments: {args.segments}")
    print(f"Output format: {args.format}")
    print(f"Output directory: {args.out}")
    _print_result(result)
    return 0


def _options_from_args(args: Namespace) -> ExportSubtitlesOptions:
    return ExportSubtitlesOptions(
        input_path=args.input,
        segments=args.segments,
        output_dir=args.out,
        video_id=args.video_id,
        language=args.lang,
        category=args.category,
    )


def _print_result(result: ExportSubtitlesResult) -> None:
    print(f"Files exported: {len(result.files)}")
    for item in result.files:
        print(
            f"JSONL written: {item.output_path} "
            f"({item.segment_count} records, {item.video_id}/{item.language}/{item.source})"
        )
