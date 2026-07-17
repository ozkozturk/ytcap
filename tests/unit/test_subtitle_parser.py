"""Subtitle parser tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap.errors import ErrorCode, YtcapError  # noqa: E402
from ytcap.models.subtitle import SubtitleCue  # noqa: E402
from ytcap.services.subtitle_parser import (  # noqa: E402
    parse_srt_file,
    parse_srt_text,
    parse_vtt_file,
    parse_vtt_text,
)


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class SubtitleParserTest(unittest.TestCase):
    def test_parse_srt_file_returns_cues(self) -> None:
        cues = parse_srt_file(FIXTURE_DIR / "sample.en.srt")

        self.assertEqual(len(cues), 3)
        self.assertEqual(
            cues[0],
            SubtitleCue(
                index=1,
                start=1.0,
                end=3.5,
                text="Hello from the first cue.",
            ),
        )
        self.assertEqual(cues[1].text, "Second cue line one.\nSecond cue line two.")
        self.assertEqual(cues[2].start, 3723.004)
        self.assertEqual(cues[2].end, 3725.006)

    def test_parse_srt_text_accepts_crlf_and_timestamp_settings(self) -> None:
        text = (
            "1\r\n"
            "00:00:01,000 --> 00:00:02,000 align:start position:0%\r\n"
            "Hello.\r\n"
        )

        cues = parse_srt_text(text)

        self.assertEqual(cues[0].index, 1)
        self.assertEqual(cues[0].start, 1.0)
        self.assertEqual(cues[0].end, 2.0)
        self.assertEqual(cues[0].text, "Hello.")

    def test_parse_srt_text_accepts_whitespace_only_separator_lines(self) -> None:
        text = (
            "1\n"
            "00:00:01,000 --> 00:00:02,000\n"
            "First.\n"
            "   \n"
            "2\n"
            "00:00:03,000 --> 00:00:04,000\n"
            "Second.\n"
        )

        cues = parse_srt_text(text)

        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[1].index, 2)
        self.assertEqual(cues[1].text, "Second.")

    def test_parse_srt_text_cleans_common_markup_and_entities(self) -> None:
        text = "1\n00:00:01,000 --> 00:00:02,000\n<i>Hello</i> &amp; goodbye.\n"

        cues = parse_srt_text(text)

        self.assertEqual(cues[0].text, "Hello & goodbye.")

    def test_parse_srt_text_returns_empty_list_for_empty_input(self) -> None:
        self.assertEqual(parse_srt_text(" \n\n "), [])

    def test_subtitle_cue_converts_to_dict(self) -> None:
        cue = SubtitleCue(index=1, start=1.25, end=2.5, text="Hello.")

        self.assertEqual(
            cue.to_dict(),
            {"index": 1, "start": 1.25, "end": 2.5, "text": "Hello."},
        )

    def test_malformed_srt_returns_controlled_parse_error(self) -> None:
        with self.assertRaises(YtcapError) as raised:
            parse_srt_file(FIXTURE_DIR / "malformed.srt")

        self.assertEqual(raised.exception.code, ErrorCode.PARSE_FAILED)
        self.assertEqual(raised.exception.exit_code, 3)
        self.assertIn("malformed SRT block 2", raised.exception.message)

    def test_end_timestamp_must_be_after_start_timestamp(self) -> None:
        text = "1\n00:00:02,000 --> 00:00:01,000\nBackwards.\n"

        with self.assertRaises(YtcapError) as raised:
            parse_srt_text(text)

        self.assertEqual(raised.exception.code, ErrorCode.PARSE_FAILED)
        self.assertIn("end timestamp must be after start timestamp", raised.exception.message)

    def test_parse_srt_text_handles_blank_lines_inside_cue(self) -> None:
        text = (
            "187\n"
            "00:09:39,480 --> 00:09:43,280\n"
            "And the Romans… lost to them.\n"
            " \n"
            "And not just a bit.\n"
        )
        cues = parse_srt_text(text)
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0].text, "And the Romans… lost to them.\nAnd not just a bit.")

    def test_parse_srt_text_handles_empty_cues(self) -> None:
        text = (
            "24\n"
            "00:02:38,040 --> 00:02:38,540\n"
        )
        cues = parse_srt_text(text)
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0].text, "")

    def test_parse_vtt_text_handles_blank_lines_inside_cue(self) -> None:
        text = (
            "WEBVTT\n\n"
            "00:09:39.480 --> 00:09:43.280\n"
            "And the Romans… lost to them.\n"
            " \n"
            "And not just a bit.\n"
        )
        cues = parse_vtt_text(text)
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0].text, "And the Romans… lost to them.\nAnd not just a bit.")

    def test_parse_vtt_text_handles_empty_cues(self) -> None:
        text = (
            "WEBVTT\n\n"
            "00:02:38.040 --> 00:02:38.540\n"
        )
        cues = parse_vtt_text(text)
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0].text, "")

    def test_parse_vtt_file_returns_cues(self) -> None:
        cues = parse_vtt_file(FIXTURE_DIR / "sample.en.vtt")

        self.assertEqual(len(cues), 3)
        self.assertEqual(
            cues[0],
            SubtitleCue(
                index=None,
                start=1.0,
                end=3.5,
                text="Hello from the first VTT cue.",
            ),
        )
        self.assertEqual(cues[1].index, None)
        self.assertEqual(cues[1].start, 4.25)
        self.assertEqual(cues[1].end, 6.0)
        self.assertEqual(cues[1].text, "Second cue line one.\nSecond cue line two.")
        self.assertEqual(cues[2].index, 3)
        self.assertEqual(cues[2].start, 3723.004)
        self.assertEqual(cues[2].end, 3725.006)

    def test_parse_vtt_text_accepts_crlf(self) -> None:
        text = "WEBVTT\r\n\r\n00:00:01.000 --> 00:00:02.000\r\nHello.\r\n"

        cues = parse_vtt_text(text)

        self.assertEqual(cues[0].start, 1.0)
        self.assertEqual(cues[0].end, 2.0)
        self.assertEqual(cues[0].text, "Hello.")

    def test_parse_vtt_text_accepts_whitespace_separators_and_note_like_ids(self) -> None:
        text = (
            "WEBVTT\n"
            "\n"
            "NOTE real comment\n"
            "ignored\n"
            " \n"
            "NOTEBOOK\n"
            "00:00:01.000 --> 00:00:02.000\n"
            "Not a note block.\n"
        )

        cues = parse_vtt_text(text)

        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0].text, "Not a note block.")

    def test_parse_vtt_text_cleans_common_markup_and_entities(self) -> None:
        text = (
            "WEBVTT\n"
            "\n"
            "00:00:01.000 --> 00:00:02.000\n"
            "<v Speaker><c.highlight>Hello</c> &amp; <00:00:01.500>goodbye.\n"
        )

        cues = parse_vtt_text(text)

        self.assertEqual(cues[0].text, "Hello & goodbye.")

    def test_parse_vtt_text_requires_header(self) -> None:
        text = "00:00:01.000 --> 00:00:02.000\nHello.\n"

        with self.assertRaises(YtcapError) as raised:
            parse_vtt_text(text)

        self.assertEqual(raised.exception.code, ErrorCode.PARSE_FAILED)
        self.assertIn("expected WEBVTT header", raised.exception.message)

    def test_malformed_vtt_returns_controlled_parse_error(self) -> None:
        with self.assertRaises(YtcapError) as raised:
            parse_vtt_file(FIXTURE_DIR / "malformed.vtt")

        self.assertEqual(raised.exception.code, ErrorCode.PARSE_FAILED)
        self.assertEqual(raised.exception.exit_code, 3)
        self.assertIn("malformed VTT block 1", raised.exception.message)


if __name__ == "__main__":
    unittest.main()
