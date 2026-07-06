"""Single-video command skeleton."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace

from ytcap.errors import ErrorCode, YtcapError
from ytcap.services.subtitle_format import validate_subtitle_format

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
    print("Video command parsed.")
    print(f"Video source: {display_video_source(args)}")
    print(f"Language: {args.lang}")
    print(f"Subtitle source: {args.source}")
    print(f"Subtitle format: {args.format}")
    print(f"Output directory: {args.out}")
    if args.dry_run:
        print("Dry run: no files written.")
    else:
        print("Extraction integration is not implemented yet.")
    return 0
