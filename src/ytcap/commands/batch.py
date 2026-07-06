"""Batch command placeholder."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace

from ytcap.errors import ErrorCode, YtcapError


def configure_parser(parser: ArgumentParser) -> None:
    parser.add_argument("--input", help="file containing URLs or IDs")
    parser.add_argument("--lang", default="en", help="subtitle language")
    parser.add_argument("--source", choices=("manual", "auto", "any"), default="any", help="subtitle source")
    parser.add_argument("--format", choices=("srt", "vtt"), default="srt", help="subtitle file format")
    parser.add_argument("--resume", action="store_true", help="continue an interrupted run")
    parser.add_argument("--skip-existing", action="store_true", help="skip existing outputs")
    parser.add_argument("--fail-fast", action="store_true", help="stop at the first error")
    parser.add_argument("--max-errors", type=int, help="stop after the given number of errors")
    parser.add_argument("--out", default="./data", help="output directory")
    parser.set_defaults(handler=handle)


def handle(args: Namespace) -> int:
    raise YtcapError(
        ErrorCode.NOT_IMPLEMENTED,
        "batch command is not implemented yet",
        exit_code=1,
    )
