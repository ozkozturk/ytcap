"""Command line entry point for ytcap."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import __version__
from .commands import batch, export, inspect, video
from .errors import ErrorCode, YtcapError, format_error
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
    try:
        args = parser.parse_args(argv)
        validate_args(args)
        return run(args)
    except YtcapError as exc:
        print(format_error(exc), file=sys.stderr)
        return exc.exit_code
