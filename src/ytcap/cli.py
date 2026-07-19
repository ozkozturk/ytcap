"""Command line entry point for ytcap."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import __version__
from .commands import batch, channel, export, inspect, playlist, video
from .errors import ErrorCode, YtcapError, format_error, format_error_json
from .logging_config import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ytcap",
        description="Extract YouTube metadata and subtitles into JSON and JSONL outputs.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ytcap {__version__}",
        help="show the installed version and exit",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="emit more detailed logs",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="emit minimal output",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="disable colored output when color support exists",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    inspect.configure_parser(subparsers.add_parser("inspect", help="inspect one video"))
    video.configure_parser(subparsers.add_parser("video", help="process one video"))
    export.configure_parser(subparsers.add_parser("export", help="convert subtitle files to JSONL"))
    batch.configure_parser(subparsers.add_parser("batch", help="process a batch file"))
    playlist.configure_parser(subparsers.add_parser("playlist", help="process a playlist"))
    channel.configure_parser(subparsers.add_parser("channel", help="process a channel"))
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.verbose and args.quiet:
        raise YtcapError(
            ErrorCode.CONFLICTING_FLAGS,
            "--verbose and --quiet cannot be used together",
            exit_code=2,
        )


def run(args: argparse.Namespace) -> int:
    configure_logging(verbose=args.verbose, quiet=args.quiet)
    if hasattr(args, "handler"):
        return args.handler(args)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = None
    try:
        args = parser.parse_args(argv)
        validate_args(args)
        return run(args)
    except YtcapError as exc:
        if args is not None and getattr(args, "json", False):
            print(format_error_json(exc), file=sys.stderr)
        else:
            print(format_error(exc), file=sys.stderr)
        return exc.exit_code
