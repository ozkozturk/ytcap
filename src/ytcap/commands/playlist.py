"""Playlist command."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace

from ytcap.app.process_playlist import ProcessPlaylistOptions, process_playlist
from ytcap.errors import ErrorCode, YtcapError
from ytcap.services.subtitle_format import validate_subtitle_format
from ytcap.services.ytdlp_adapter import VideoSource, YtDlpAdapter


def configure_parser(parser: ArgumentParser) -> None:
    parser.add_argument("--url", help="YouTube playlist URL")
    parser.add_argument("--id", dest="playlist_id", help="YouTube playlist ID")
    parser.add_argument("--lang", default="en", help="subtitle language")
    parser.add_argument("--source", choices=("manual", "auto", "any"), default="any", help="subtitle source")
    parser.add_argument("--format", default="srt", help="subtitle file format")
    parser.add_argument("--limit", type=int, help="maximum number of videos to process")
    parser.add_argument("--start", type=int, default=1, help="start index (1-based)")
    parser.add_argument("--end", type=int, help="end index (inclusive)")
    parser.add_argument("--out", default="./data", help="output directory")
    parser.add_argument("--skip-existing", action="store_true", help="skip existing outputs")
    parser.add_argument("--fail-fast", action="store_true", help="stop at the first error")
    parser.add_argument("--max-errors", type=int, help="stop after the given number of errors")
    parser.add_argument("--resume", action="store_true", help="continue an interrupted run")
    parser.add_argument("--dry-run", action="store_true", help="show planned work without writing files")
    parser.set_defaults(handler=handle)


def handle(args: Namespace) -> int:
    if args.url and args.playlist_id:
        raise YtcapError(
            ErrorCode.CONFLICTING_FLAGS,
            "--url and --id cannot be used together",
            exit_code=2,
        )
    if not args.url and not args.playlist_id:
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            "one of --url or --id is required",
            exit_code=2,
        )
    if args.max_errors is not None and args.max_errors < 1:
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            "--max-errors must be a positive integer",
            exit_code=2,
        )
    if args.start < 1:
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            "--start must be a positive integer",
            exit_code=2,
        )
    if args.end is not None and args.end < args.start:
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            "--end must be >= --start",
            exit_code=2,
        )
    if args.limit is not None and args.limit < 1:
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            "--limit must be a positive integer",
            exit_code=2,
        )
    if args.skip_existing and args.resume:
        raise YtcapError(
            ErrorCode.CONFLICTING_FLAGS,
            "--skip-existing and --resume cannot be used together",
            exit_code=2,
        )
    validate_subtitle_format(args.format)

    if args.url:
        playlist_url = args.url
    else:
        playlist_url = f"https://www.youtube.com/playlist?list={args.playlist_id}"

    options = ProcessPlaylistOptions(
        url=playlist_url,
        language=args.lang,
        source=args.source,
        subtitle_format=args.format,
        output_dir=args.out,
        limit=args.limit,
        start=args.start,
        end=args.end,
        skip_existing=args.skip_existing,
        fail_fast=args.fail_fast,
        max_errors=args.max_errors,
        resume=args.resume,
        dry_run=args.dry_run,
    )

    result = process_playlist(options, adapter=YtDlpAdapter())

    if args.dry_run:
        print("Dry run: no files written.")
        print(f"Total videos in playlist: {result.total}")
        print(f"Videos to process: {result.ok}")
        print(f"Videos to skip: {result.skipped}")
        return 0

    print("Playlist command completed.")
    print(f"Total: {result.total}")
    print(f"Success: {result.ok}")
    print(f"Skipped: {result.skipped}")
    print(f"Failed: {result.failed}")
    print(f"Manifest: {result.manifest_path}")

    if result.failed > 0:
        return 1
    return 0
