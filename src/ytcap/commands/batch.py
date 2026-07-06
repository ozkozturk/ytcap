"""Batch command."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace

from ytcap.app.process_batch import ProcessBatchOptions, process_batch
from ytcap.errors import ErrorCode, YtcapError
from ytcap.services.subtitle_format import validate_subtitle_format
from ytcap.services.ytdlp_adapter import YtDlpAdapter


def configure_parser(parser: ArgumentParser) -> None:
    parser.add_argument("--input", help="file containing URLs or IDs")
    parser.add_argument("--lang", default="en", help="subtitle language")
    parser.add_argument("--source", choices=("manual", "auto", "any"), default="any", help="subtitle source")
    parser.add_argument("--format", default="srt", help="subtitle file format")
    parser.add_argument("--resume", action="store_true", help="continue an interrupted run")
    parser.add_argument("--skip-existing", action="store_true", help="skip existing outputs")
    parser.add_argument("--fail-fast", action="store_true", help="stop at the first error")
    parser.add_argument("--max-errors", type=int, help="stop after the given number of errors")
    parser.add_argument("--out", default="./data", help="output directory")
    parser.add_argument("--dry-run", action="store_true", help="show planned work without writing files")
    parser.set_defaults(handler=handle)


def handle(args: Namespace) -> int:
    if not args.input:
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            "--input file must be specified",
            exit_code=2,
        )
    if args.max_errors is not None and args.max_errors < 1:
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            "--max-errors must be a positive integer",
            exit_code=2,
        )
    validate_subtitle_format(args.format)

    options = ProcessBatchOptions(
        input=args.input,
        language=args.lang,
        source=args.source,
        subtitle_format=args.format,
        output_dir=args.out,
        resume=args.resume,
        skip_existing=args.skip_existing,
        fail_fast=args.fail_fast,
        max_errors=args.max_errors,
        dry_run=args.dry_run,
    )

    result = process_batch(options, adapter=YtDlpAdapter())

    if args.dry_run:
        print("Dry run: no files written.")
        print(f"Total videos in batch: {result.total}")
        print(f"Videos to process: {result.ok}")
        print(f"Videos to skip: {result.skipped}")
        return 0

    print("Batch command completed.")
    print(f"Total: {result.total}")
    print(f"Success: {result.ok}")
    print(f"Skipped: {result.skipped}")
    print(f"Failed: {result.failed}")
    print(f"Manifest: {result.manifest_path}")

    if result.failed > 0:
        return 1
    return 0
