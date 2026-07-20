"""Sentence artifact verification command."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace

from ytcap.exporters.sentence_artifact import verify_sentence_artifact


def configure_parser(parser: ArgumentParser) -> None:
    parser.add_argument(
        "--manifest",
        required=True,
        help="sentence artifact manifest JSON path",
    )
    parser.set_defaults(handler=handle)


def handle(args: Namespace) -> int:
    manifest = verify_sentence_artifact(args.manifest)
    identity = manifest["identity"]
    output = manifest["output"]
    print("Verification complete.")
    print(f"Manifest: {args.manifest}")
    print(f"JSONL: {output['filename']}")
    print(f"Records: {output['record_count']}")
    print(
        "Identity: "
        f"{identity['video_id']}/{identity['language']}/{identity['source']}"
    )
    return 0
