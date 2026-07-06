"""Export command skeleton."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace


def configure_parser(parser: ArgumentParser) -> None:
    parser.add_argument("--input", required=True, help="SRT/VTT file or directory")
    parser.add_argument("--segments", choices=("cue", "sentence"), default="cue", help="segment type")
    parser.add_argument("--format", choices=("jsonl",), default="jsonl", help="output format")
    parser.add_argument("--out", default="./data/normalized", help="output directory")
    parser.add_argument("--video-id", help="video ID override for a single file")
    parser.add_argument("--lang", help="language override")
    parser.set_defaults(handler=handle)


def handle(args: Namespace) -> int:
    print("Export command parsed.")
    print(f"Input: {args.input}")
    print(f"Segments: {args.segments}")
    print(f"Output format: {args.format}")
    print(f"Output directory: {args.out}")
    print("Subtitle parsing and JSONL export are not implemented yet.")
    return 0
