# ytcap

`ytcap` is a Python CLI project for extracting **video metadata** and **subtitle files** from YouTube video, batch, and playlist sources, then turning them into reusable JSON and JSONL outputs.

It is designed for workflows where you have YouTube video URLs, video IDs, or playlists and want structured metadata plus subtitles for search, indexing, dataset preparation, education, or analysis.

## Project Status

The current public release is:

```text
0.1.2
```

Release pages:

- PyPI: <https://pypi.org/project/ytcap/>
- GitHub Releases: <https://github.com/ozkozturk/ytcap/releases>

Release automation uses GitHub Actions with PyPI and TestPyPI Trusted
Publishing. See `RELEASE.md` for the maintainer release process.

`ytcap` is still pre-1.0, so CLI details and JSON/JSONL schemas may change in
future `0.x` releases. User-facing changes are tracked in `CHANGELOG.md`.

The current release includes:

- Importable Python package scaffold.
- Package version exposed as `ytcap.__version__`.
- Basic CLI entry point with `ytcap --help` and `ytcap --version`.
- CLI command structure for `inspect`, `video`, and `export`.
- `batch` command to process multiple video URLs or IDs from a text file, with run manifest logging, `--resume` and `--skip-existing` support.
- `yt-dlp` adapter support for `inspect` metadata extraction.
- Normalized video metadata mapping and inspect JSON summary output.
- Tested subtitle source selection for `manual`, `auto`, and `any` normalized tracks.
- Controlled subtitle format validation for `srt` and `vtt`.
- Standard output directory layout creation for `video --out`.
- `video` command metadata JSON writing and selected SRT/VTT subtitle file download.
- SRT/VTT cue parsing, cue-level JSONL writer helpers, and basic sentence-level segmentation helpers.
- `export` command conversion of existing SRT/VTT files to enriched cue-level or sentence-level JSONL.
- `playlist` command to process videos inside a YouTube playlist with `--limit`, `--start`, and `--end` range controls, run manifest logging, `--resume`, `--skip-existing`, and `--dry-run`.
- Safe validation for dynamic output filename parts to prevent path traversal from user input or extractor metadata.
- English manual subtitle variant matching for `--lang en`, including `en-*`
  tracks such as `en-GB`.
- GitHub Actions release automation with Trusted Publishing.

## Core Decisions

| Decision | Target |
|---|---|
| Language | Python |
| Minimum Python version | Python 3.11+ |
| CLI approach | Standard library first: `argparse` |
| Test approach | Standard library first: `unittest` |
| YouTube Data API | Not used |
| Metadata and subtitle extraction | `yt-dlp>=2026.06.09` is the core extractor dependency |
| Video/audio downloads | Out of scope for the MVP |
| Output format | JSON for metadata, JSONL for segment and sentence output |
| Distribution target | PyPI and `pipx install ytcap` |
| Additional dependencies | Require justification and approval before being added |

## Current Capabilities and Roadmap

The current release can:

- Accept a single YouTube video URL or video ID.
- Save normalized video metadata as JSON.
- Find subtitles for a requested language.
- Prefer manual subtitles when available, with optional fallback to automatic subtitles.
- Save subtitles as SRT or VTT.
- Convert subtitles to cue-level or sentence-level JSONL.
- Report videos with missing or failed subtitle extraction.
- Process a text batch file of video URLs or IDs.
- Process a YouTube playlist with range and limit controls.

Later releases may add:

- A dedicated retry command for failed records.
- A stable `1.0` CLI and JSON/JSONL schema.

## Non-Goals

`ytcap` intentionally does not:

- Use the official YouTube Data API.
- Manage API keys or OAuth flows.
- Download video or audio files as an MVP goal.
- Redistribute YouTube content or bypass access restrictions.
- Start with advanced NLP sentence segmentation libraries; simple, testable heuristics come first.

## CLI Examples

These commands show the current user experience. The `inspect` command uses
`yt-dlp` for metadata and subtitle availability summaries. The `video` command
extracts metadata through `yt-dlp`, writes normalized metadata JSON, selects a
matching subtitle track,
and saves the selected SRT/VTT subtitle file. SRT/VTT cue parsers,
cue-level JSONL writer helpers, and basic punctuation-based sentence
segmentation helpers are wired into the `export` command for existing
subtitle files.

### Inspect One Video

```bash
ytcap inspect --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

This answers:

- Is the video reachable?
- Can metadata be extracted?
- Which subtitle languages are available?
- Are subtitles manual, automatic, or both?

### Extract Metadata and Subtitles

```bash
ytcap video --url "https://www.youtube.com/watch?v=VIDEO_ID" --lang en --source any --format srt --out ./data
```

| Part | Meaning |
|---|---|
| `ytcap` | CLI application |
| `video` | Single-video processing command |
| `--url` | Video URL |
| `--lang en` | Request English subtitles |
| `--source any` | Try manual subtitles first, then automatic subtitles |
| `--format srt` | Save subtitles as SRT |
| `--out ./data` | Write outputs under `./data` |

Implemented source selection behavior uses language and format matches:
`manual` selects only manual subtitles, `auto` selects only automatic subtitles,
and `any` tries manual first before falling back to automatic subtitles. For
`--lang en`, manual English variants reported by YouTube as `en-*`, such as
`en-GB` or `en-eEY6OEpapP`, are accepted while output file names still use the
requested `en` language component.
Implemented subtitle format validation currently accepts `srt` and `vtt`; other
values return an `UNSUPPORTED_FORMAT` error before extraction work starts.
When run without `--dry-run`, `video` writes normalized metadata to
`videos/{video_id}.info.json` and the selected subtitle file to
`subtitles/{video_id}.{lang}.{source}.{format}` under the output directory.
If the requested subtitle cannot be selected or downloaded, the command returns
a controlled error without leaving a new partial metadata file behind.

### List Available Subtitles

```bash
ytcap inspect --url "https://www.youtube.com/watch?v=VIDEO_ID" --list-subs
```

### Convert Existing Subtitles to JSONL

```bash
ytcap export --input ./data/subtitles/VIDEO_ID.en.manual.srt --segments cue --category education --out ./data/normalized
```

```bash
ytcap export --input ./data/subtitles --segments sentence --out ./data/normalized
```

The `export` command reads existing `.srt` and `.vtt` files and writes enriched
JSONL records to `{video_id}.{lang}.{segments}.jsonl` under the output
directory. It infers `video_id`, language, and source from names such as
`VIDEO_ID.en.manual.srt`; when the source is missing, JSONL records use
`"source":"unknown"`. `--video-id` and `--lang` may override metadata for a
single file input.

Export expects the matching normalized metadata file at
`videos/{video_id}.info.json` in the standard output layout. Each JSONL record
keeps the display `text`, adds a search-friendly `normalized_text`, and copies
compact video, channel, available manual subtitle language, and downloaded
subtitle language metadata from that file. English subtitle languages (`en` and
`en-*`) are excluded from the subtitle language arrays. When `--category` is
provided, JSONL records include `dataset_category` with that value and
`category_source:"user"`; otherwise those fields are `null` and `"none"`.

Dynamic filename parts such as video ID, language, source, format, segment type,
and run ID are validated before paths are built. Empty values, path separators,
control characters, absolute paths, `.` and `..` are rejected.

### Process a Batch File

```bash
ytcap batch --input videos.txt --lang en --source any --format srt --resume --skip-existing --out ./data
```

This command parses the input file and processes each URL/ID. It creates a run
manifest under `runs/{run_id}.manifest.json` keeping track of execution
statistics, output files, and errors. Failed attempts are appended to
`failed/failed.jsonl`. `--resume` skips entries completed in the latest
manifest and retries previous failures, while `--skip-existing` skips videos
whose metadata and subtitle files already exist for the requested language,
source, and format. `--dry-run` reports the batch plan without writing files or
creating output directories.

#### Batch Input File Format

The `--input` file for the `batch` command is a plain text file containing one YouTube video URL or video ID per line.
- Empty lines and lines containing only whitespace are ignored.
- Lines starting with `#` (with optional leading whitespace) are ignored as comment lines.
- Inline comments starting with `#` are supported, and the comment text plus any preceding whitespace are ignored.

Example input file:
```text
# This is a comment line
dQw4w9WgXcQ                  # Rick Astley - Never Gonna Give You Up
https://youtu.be/jNQXAC9IVRw # Another video URL
```

### Process a Playlist

```bash
ytcap playlist --url "https://www.youtube.com/playlist?list=PLAYLIST_ID" --start 1 --limit 50 --lang en --source any --format srt --out ./data
```

The `playlist` command uses `yt-dlp` flat playlist extraction to collect video
entries without the official YouTube Data API, then processes each video with
the same metadata and subtitle flow as `video`. `--start` is 1-based, `--end`
is inclusive, and `--limit` caps the selected range. `--resume` continues only
from a matching playlist run manifest, while `--skip-existing` skips videos
only when matching metadata and subtitle files already exist.


## Output Layout

```text
data/
  videos/
    VIDEO_ID.info.json
  subtitles/
    VIDEO_ID.en.manual.srt
  normalized/
    VIDEO_ID.en.cue.jsonl
  runs/
    RUN_ID.manifest.json
  failed/
    failed.jsonl
```

Example cue-level JSONL line:

```json
{"schema_version":"0.1","type":"cue","video_id":"VIDEO_ID","language":"en","source":"manual","start":1.0,"end":3.5,"text":"Example subtitle text.","normalized_text":"example subtitle text","cue_index":1,"channel_id":"channel123","channel_name":"Example Channel","channel_url":"https://www.youtube.com/channel/channel123","video_title":"Example Video","video_url":"https://www.youtube.com/watch?v=VIDEO_ID","video_webpage_url":"https://www.youtube.com/watch?v=VIDEO_ID","video_duration_seconds":320,"video_upload_date":"20260101","available_manual_subtitles":["tr"],"downloaded_subtitles":["tr"],"dataset_category":"education","category_source":"user"}
```

Sentence-level segmentation uses a simple standard-library heuristic that
splits on `.`, `?`, and `!`. Timing is marked with a strategy such as
`cue_exact`, `cue_merge`, `heuristic`, or `unknown` because sentence boundaries
can fall inside or across subtitle cues.

## Documentation

| File | Purpose |
|---|---|
| `USAGE.md` | Usage boundaries, limitations, and responsible use notes |
| `CLI_REFERENCE.md` | Commands, flags, behavior, and error codes |
| `OUTPUT_FORMAT.md` | Target JSON and JSONL output formats |
| `RELEASE.md` | Packaging, Trusted Publishing, and release process |
| `CONTRIBUTING.md` | Contributor expectations |
| `SECURITY.md` | Security policy and sensitive data rules |

## Development Install

For local development, use Python 3.11 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

This installs `yt-dlp>=2026.06.09` as the runtime extractor dependency. Unit
tests use fixtures and mocks instead of making real YouTube or network calls.

Smoke-test the current CLI:

```bash
ytcap --help
ytcap --version
```

## Installation

Recommended installation from PyPI:

```bash
pipx install ytcap
```

Alternative:

```bash
python -m pip install ytcap
```

Expected usage:

```bash
ytcap --help
```

```bash
ytcap video --url "https://www.youtube.com/watch?v=VIDEO_ID" --lang en --source any
```

## License

This project is released under the MIT License. See `LICENSE.md` for details.
