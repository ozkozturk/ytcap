"""Sentence artifact contract tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap import __version__  # noqa: E402
from ytcap.errors import ErrorCode, YtcapError  # noqa: E402
from ytcap.app.export_subtitles import ExportSubtitlesOptions, export_subtitles  # noqa: E402
from ytcap.exporters.sentence_artifact import (  # noqa: E402
    MANIFEST_SCHEMA_VERSION,
    sha256_bytes,
    verify_sentence_artifact,
    write_sentence_artifact,
)
from ytcap.models.export_enrichment import EXPORT_ENRICHMENT_DEFAULTS  # noqa: E402
from ytcap.models.subtitle import SubtitleSentence  # noqa: E402


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "sentence_contract"


def sentence(
    index: int,
    *,
    start: float = 1.0,
    end: float = 2.0,
    text: str = "A sentence.",
    precision: str = "cue_aligned",
) -> SubtitleSentence:
    return SubtitleSentence(
        index=index,
        start=start,
        end=end,
        text=text,
        timing_strategy="cue_exact" if precision == "cue_aligned" else "heuristic",
        playback_start=max(0.0, start - 0.25),
        playback_end=end + 0.40,
        cue_coverage="single",
        timing_precision=precision,
        start_cue_index=index,
        end_cue_index=index,
        cue_count=1,
        start_char_in_first_cue=0,
        end_char_in_last_cue=len(text),
        boundary_engine="punctuation-v2",
    )


def write_inputs(root: Path, *, video_id: str = "contract001", language: str = "en") -> tuple[Path, Path]:
    subtitle_path = root / "subtitles" / f"{video_id}.{language}.manual.srt"
    metadata_path = root / "videos" / f"{video_id}.info.json"
    subtitle_path.parent.mkdir(parents=True)
    metadata_path.parent.mkdir(parents=True)
    subtitle_path.write_bytes(b"1\n00:00:01,000 --> 00:00:02,000\nA sentence.\n")
    metadata_path.write_bytes(b'{"schema_version":"0.1"}\n')
    return subtitle_path, metadata_path


class SentenceArtifactTest(unittest.TestCase):
    def test_committed_bundle_is_the_public_contract_golden(self) -> None:
        fixture_manifest = (
            FIXTURE_ROOT / "normalized" / "fixture001.en.sentence.manifest.json"
        )
        verify_sentence_artifact(fixture_manifest)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "subtitles" / "fixture001.en.manual.srt"
            metadata_path = root / "videos" / "fixture001.info.json"
            subtitle_path.parent.mkdir(parents=True)
            metadata_path.parent.mkdir(parents=True)
            subtitle_path.write_bytes(
                (FIXTURE_ROOT / "subtitles" / subtitle_path.name).read_bytes()
            )
            metadata_path.write_bytes(
                (FIXTURE_ROOT / "videos" / metadata_path.name).read_bytes()
            )

            result = export_subtitles(
                ExportSubtitlesOptions(
                    input_path=subtitle_path,
                    segments="sentence",
                    output_dir=root / "normalized",
                )
            )
            generated_output = result.files[0].output_path
            generated_manifest = result.files[0].manifest_path

            self.assertEqual(
                generated_output.read_bytes(),
                (FIXTURE_ROOT / "normalized" / generated_output.name).read_bytes(),
            )
            self.assertIsNotNone(generated_manifest)
            self.assertEqual(
                generated_manifest.read_bytes(),
                fixture_manifest.read_bytes(),
            )

    def test_writes_deterministic_jsonl_and_manifest_contract(self) -> None:
        artifacts: list[tuple[bytes, bytes]] = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                subtitle_path, metadata_path = write_inputs(root)
                output_path = root / "normalized" / "contract001.en.sentence.jsonl"

                manifest_path = write_sentence_artifact(
                    output_path,
                    [sentence(1)],
                    source_path=subtitle_path,
                    video_id="contract001",
                    language="en",
                    source="manual",
                    metadata_enrichment=EXPORT_ENRICHMENT_DEFAULTS,
                    metadata_path=metadata_path,
                )

                manifest = verify_sentence_artifact(manifest_path)
                jsonl_bytes = output_path.read_bytes()
                manifest_bytes = manifest_path.read_bytes()
                artifacts.append((jsonl_bytes, manifest_bytes))
                self.assertEqual(manifest["schema_version"], MANIFEST_SCHEMA_VERSION)
                self.assertEqual(manifest["producer"]["version"], __version__)
                self.assertEqual(manifest["output"]["schema_version"], "0.1")
                self.assertEqual(manifest["output"]["sha256"], sha256_bytes(jsonl_bytes))
                self.assertEqual(manifest["input"]["sha256"], sha256_bytes(subtitle_path.read_bytes()))
                self.assertEqual(manifest["metadata"]["sha256"], sha256_bytes(metadata_path.read_bytes()))
                self.assertEqual(manifest["input"]["filename"], "../subtitles/contract001.en.manual.srt")
                self.assertEqual(manifest["metadata"]["filename"], "../videos/contract001.info.json")
                self.assertNotIn(str(root), manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(artifacts[0], artifacts[1])

    def test_allows_missing_metadata_and_preserves_null_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "track.en-GB.srt"
            subtitle_path.write_text("source", encoding="utf-8")
            output_path = root / "out" / "track.en-GB.sentence.jsonl"

            manifest_path = write_sentence_artifact(
                output_path,
                [sentence(1)],
                source_path=subtitle_path,
                video_id="track",
                language="en-GB",
                source="unknown",
                metadata_enrichment=EXPORT_ENRICHMENT_DEFAULTS,
            )

            manifest = verify_sentence_artifact(manifest_path)
            record = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["identity"]["language"], "en-GB")
            self.assertEqual(manifest["identity"]["source"], "unknown")
            self.assertEqual(manifest["metadata"], {"filename": None, "sha256": None})
            self.assertIsNone(record["video_title"])
            self.assertIsNone(record["channel_id"])

    def test_quality_summary_reports_all_precision_and_suspicious_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "source.srt"
            subtitle_path.write_text("source", encoding="utf-8")
            output_path = root / "quality.en.sentence.jsonl"
            precisions = (
                "cue_aligned",
                "estimated_start",
                "estimated_end",
                "estimated_both",
                "unknown",
            )
            records = [
                sentence(index, start=float(index), end=float(index + 1), precision=precision)
                for index, precision in enumerate(precisions, start=1)
            ]
            records[1] = sentence(2, start=2.0, end=2.0, text="", precision="estimated_start")
            records[2] = sentence(3, start=1.5, end=3.0, precision="estimated_end")

            manifest_path = write_sentence_artifact(
                output_path,
                records,
                source_path=subtitle_path,
                video_id="quality",
                language="en",
                source="auto",
                metadata_enrichment=EXPORT_ENRICHMENT_DEFAULTS,
            )
            summary = json.loads(manifest_path.read_text(encoding="utf-8"))["quality_summary"]

            for precision in precisions:
                self.assertEqual(summary[precision], 1)
            self.assertEqual(summary["empty_text"], 1)
            self.assertEqual(summary["non_positive_duration"], 1)
            self.assertEqual(summary["overlap_with_previous"], 1)

    def test_export_reports_overlap_from_overlapping_source_cues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "subtitles" / "overlap.en.manual.srt"
            subtitle_path.parent.mkdir(parents=True)
            subtitle_path.write_text(
                "1\n00:00:00,000 --> 00:00:05,000\nOne.\n\n"
                "2\n00:00:02,000 --> 00:00:04,000\nTwo.\n",
                encoding="utf-8",
            )

            result = export_subtitles(
                ExportSubtitlesOptions(
                    input_path=subtitle_path,
                    segments="sentence",
                    output_dir=root / "normalized",
                )
            )
            manifest_path = result.files[0].manifest_path
            self.assertIsNotNone(manifest_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(manifest["quality_summary"]["overlap_with_previous"], 1)

    def test_tampered_jsonl_fails_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "source.srt"
            subtitle_path.write_text("source", encoding="utf-8")
            output_path = root / "tamper.en.sentence.jsonl"
            manifest_path = write_sentence_artifact(
                output_path,
                [sentence(1)],
                source_path=subtitle_path,
                video_id="tamper",
                language="en",
                source="manual",
                metadata_enrichment=EXPORT_ENRICHMENT_DEFAULTS,
            )
            output_path.write_bytes(output_path.read_bytes() + b"\n")

            with self.assertRaises(YtcapError) as raised:
                verify_sentence_artifact(manifest_path)

            self.assertEqual(raised.exception.code, ErrorCode.PARSE_FAILED)
            self.assertIn("SHA-256", raised.exception.message)

    def test_mixed_identity_is_rejected_even_with_matching_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "source.srt"
            subtitle_path.write_text("source", encoding="utf-8")
            output_path = root / "mixed.en.sentence.jsonl"
            manifest_path = write_sentence_artifact(
                output_path,
                [sentence(1)],
                source_path=subtitle_path,
                video_id="mixed",
                language="en",
                source="manual",
                metadata_enrichment=EXPORT_ENRICHMENT_DEFAULTS,
            )
            record = json.loads(output_path.read_text(encoding="utf-8"))
            record["video_id"] = "different"
            output_bytes = (
                json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            ).encode("utf-8")
            output_path.write_bytes(output_bytes)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["output"]["sha256"] = sha256_bytes(output_bytes)
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(YtcapError) as raised:
                verify_sentence_artifact(manifest_path)

            self.assertIn("mixed sentence artifact identity", raised.exception.message)

    def test_publish_failure_leaves_no_final_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "source.srt"
            subtitle_path.write_text("source", encoding="utf-8")
            output_path = root / "atomic.en.sentence.jsonl"
            manifest_path = output_path.with_suffix(".manifest.json")
            original_replace = Path.replace

            def fail_manifest_replace(path: Path, target: Path) -> Path:
                if Path(target) == manifest_path:
                    raise OSError("synthetic manifest publish failure")
                return original_replace(path, target)

            with patch("pathlib.Path.replace", autospec=True, side_effect=fail_manifest_replace):
                with self.assertRaises(YtcapError) as raised:
                    write_sentence_artifact(
                        output_path,
                        [sentence(1)],
                        source_path=subtitle_path,
                        video_id="atomic",
                        language="en",
                        source="manual",
                        metadata_enrichment=EXPORT_ENRICHMENT_DEFAULTS,
                    )

            self.assertEqual(raised.exception.code, ErrorCode.OUTPUT_WRITE_FAILED)
            self.assertFalse(output_path.exists())
            self.assertFalse(manifest_path.exists())


if __name__ == "__main__":
    unittest.main()
