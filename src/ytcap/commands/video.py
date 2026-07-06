"""Single-video command."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace

from ytcap.app.process_video import ProcessVideoOptions, ProcessVideoResult, process_video
from ytcap.errors import ErrorCode, YtcapError
from ytcap.services.subtitle_format import validate_subtitle_format
from ytcap.services.ytdlp_adapter import YtDlpAdapter

from .common import display_video_source, require_video_source


def configure_parser(parser: ArgumentParser) -> None:
    parser.add_argument("--url", help="YouTube video URL")
    parser.add_argument("--id", dest="video_id", help="YouTube video ID")
    parser.add_argument("--lang", default="en", help="subtitle language")
    parser.add_argument("--source", choices=("manual", "auto", "any"), default="any", help="subtitle source")
    parser.add_argument("--format", default="srt", help="subtitle file format")
    parser.add_argument("--out", default="./data", help="output directory")
    parser.add_argument("--metadata-only", action="store_true", help="write only metadata")
    parser.add_argument("--subs-only", action="store_true", help="write only subtitles")
    parser.add_argument("--skip-existing", action="store_true", help="skip existing output")
    parser.add_argument("--overwrite", action="store_true", help="rewrite existing output")
    parser.add_argument("--dry-run", action="store_true", help="show planned work without writing files")
    parser.set_defaults(handler=handle)


def validate_video_args(args: Namespace) -> None:
    require_video_source(args)
    validate_subtitle_format(args.format)
    if args.skip_existing and args.overwrite:
        raise YtcapError(
            ErrorCode.CONFLICTING_FLAGS,
            "--skip-existing and --overwrite cannot be used together",
            exit_code=2,
        )
    if args.metadata_only and args.subs_only:
        raise YtcapError(
            ErrorCode.CONFLICTING_FLAGS,
            "--metadata-only and --subs-only cannot be used together",
            exit_code=2,
        )


def handle(args: Namespace) -> int:
    validate_video_args(args)
    result = process_video(_options_from_args(args), adapter=YtDlpAdapter())
    print("Video command parsed.")
    print(f"Video source: {display_video_source(args)}")
    print(f"Language: {args.lang}")
    print(f"Subtitle source: {args.source}")
    print(f"Subtitle format: {args.format}")
    print(f"Output directory: {args.out}")
    _print_result(result)
    return 0


def _options_from_args(args: Namespace) -> ProcessVideoOptions:
    return ProcessVideoOptions(
        url=args.url,
        video_id=args.video_id,
        language=args.lang,
        source=args.source,
        subtitle_format=args.format,
        output_dir=args.out,
        metadata_only=args.metadata_only,
        subs_only=args.subs_only,
        skip_existing=args.skip_existing,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )


def _print_result(result: ProcessVideoResult) -> None:
    if result.dry_run:
        print("Dry run: no files written.")
        if result.metadata_path is not None:
            print(f"Metadata output: {result.metadata_path}")
        if result.subtitle_path is not None:
            print(f"Subtitle output: {result.subtitle_path}")
        elif result.subtitle_requested and result.selected_source is None:
            print("Subtitle output: selected after metadata inspection.")
        return

    print("Output directories prepared.")
    if result.wrote_metadata:
        print(f"Metadata written: {result.metadata_path}")
    elif result.skipped_metadata:
        print(f"Metadata skipped: {result.metadata_path}")

    if result.wrote_subtitle:
        print(f"Subtitle written: {result.subtitle_path}")
    elif result.skipped_subtitle:
        print(f"Subtitle skipped: {result.subtitle_path}")
