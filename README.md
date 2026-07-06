# ytcap

`ytcap` is a Python CLI project for extracting **video metadata** and **subtitle files** from YouTube video, batch, and playlist sources, then turning them into reusable JSON and JSONL outputs.

It is designed for workflows where you have YouTube video URLs, video IDs, or playlists and want structured metadata plus subtitles for search, indexing, dataset preparation, education, or analysis.

## Project Status

This repository is in an early planning and implementation stage. The first target release is:

```text
0.1.0
```

Currently implemented:

- Importable Python package scaffold.
- Package version exposed as `ytcap.__version__`.
- Basic CLI entry point with `ytcap --help` and `ytcap --version`.
- CLI command structure for `inspect`, `video`, and `export`.
- A `batch` placeholder that clearly reports the command is not implemented yet.
- `yt-dlp` adapter support for `inspect` metadata extraction.
- Normalized video metadata mapping and inspect JSON summary output.
- Tested subtitle source selection for `manual`, `auto`, and `any` normalized tracks.
- Controlled subtitle format validation for `srt` and `vtt`.
- Standard output directory layout creation for `video --out`.
- `video` command metadata JSON writing and selected SRT/VTT subtitle file download.
- SRT/VTT cue parsing, cue-level JSONL writer helpers, and basic sentence-level segmentation helpers.
- `export` command conversion of existing SRT/VTT files to cue-level or sentence-level JSONL.

## Core Decisions

| Decision | Target |
|---|---|
| Language | Python |
| Minimum Python version | Python 3.11+ |
| CLI approach | Standard library first: `argparse` |
| Test approach | Standard library first: `unittest` |
| YouTube Data API | Not used |
| Metadata and subtitle extraction | `yt-dlp` is the core extractor dependency |
| Video/audio downloads | Out of scope for the MVP |
| Output format | JSON for metadata, JSONL for segment and sentence output |
| Distribution target | PyPI and `pipx install ytcap` |
| Additional dependencies | Require justification and approval before being added |

## Planned Capabilities

The MVP is intended to:

- Accept a single YouTube video URL or video ID.
- Save normalized video metadata as JSON.
- Find subtitles for a requested language.
- Prefer manual subtitles when available, with optional fallback to automatic subtitles.
- Save subtitles as SRT or VTT.
- Convert subtitles to cue-level or sentence-level JSONL.
- Report videos with missing or failed subtitle extraction.

Later releases may add:

- Batch file input.
- Playlist processing.
- Resume and skip-existing behavior.
- Retry support for failed records.
- PyPI publication.
- Automated test and release workflows through GitHub Actions.

## Non-Goals

`ytcap` intentionally does not:

- Use the official YouTube Data API.
- Manage API keys or OAuth flows.
- Download video or audio files as an MVP goal.
- Redistribute YouTube content or bypass access restrictions.
- Start with advanced NLP sentence segmentation libraries; simple, testable heuristics come first.

## Planned CLI Examples

These commands show the intended user experience. Some commands may not be implemented yet.
The current `inspect` command uses `yt-dlp` for metadata and subtitle
availability summaries. The `video` command extracts metadata through
`yt-dlp`, writes normalized metadata JSON, selects a matching subtitle track,
and saves the selected SRT/VTT subtitle file. SRT/VTT cue parsers,
cue-level JSONL writer helpers, and basic punctuation-based sentence
segmentation helpers are wired into the `export` command for existing
subtitle files.

### Inspect One Video

```bash
ytcap inspect --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

This should answer:

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

Implemented source selection behavior uses exact language and format matches:
`manual` selects only manual subtitles, `auto` selects only automatic subtitles,
and `any` tries manual first before falling back to automatic subtitles.
Implemented subtitle format validation currently accepts `srt` and `vtt`; other
values return an `UNSUPPORTED_FORMAT` error before extraction work starts.
When run without `--dry-run`, `video` writes normalized metadata to
`videos/{video_id}.info.json` and the selected subtitle file to
`subtitles/{video_id}.{lang}.{source}.{format}` under the output directory.

### List Available Subtitles

```bash
ytcap inspect --url "https://www.youtube.com/watch?v=VIDEO_ID" --list-subs
```

### Convert Existing Subtitles to JSONL

```bash
ytcap export --input ./data/subtitles/VIDEO_ID.en.manual.srt --segments cue --out ./data/normalized
```

```bash
ytcap export --input ./data/subtitles --segments sentence --out ./data/normalized
```

The `export` command reads existing `.srt` and `.vtt` files and writes JSONL
records to `{video_id}.{lang}.{segments}.jsonl` under the output directory. It
infers `video_id`, language, and source from names such as
`VIDEO_ID.en.manual.srt`; when the source is missing, JSONL records use
`"source":"unknown"`. `--video-id` and `--lang` may override metadata for a
single file input.

### Process a Batch File

```bash
ytcap batch --input videos.txt --lang en --source any --format srt --resume --skip-existing --out ./data
```

This command is a later release target. The current placeholder returns a clear
not-implemented error.

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


## Planned Output Layout

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
{"schema_version":"0.1","type":"cue","video_id":"VIDEO_ID","language":"en","source":"manual","start":1.0,"end":3.5,"text":"Example subtitle text.","cue_index":1}
```

Sentence-level segmentation uses a simple standard-library heuristic that
splits on `.`, `?`, and `!`. Timing is marked with a strategy such as
`cue_exact`, `cue_merge`, `heuristic`, or `unknown` because sentence boundaries
can fall inside or across subtitle cues.

## Documentation

| File | Purpose |
|---|---|
| `USAGE.md` | Usage boundaries, limitations, and responsible use notes |
| `CLI_REFERENCE.md` | Planned commands, flags, behavior, and error codes |
| `OUTPUT_FORMAT.md` | Target JSON and JSONL output formats |
| `RELEASE.md` | Packaging and release process |
| `CONTRIBUTING.md` | Contributor expectations |
| `SECURITY.md` | Security policy and sensitive data rules |

## Development Install

For local development, use Python 3.11 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

This installs `yt-dlp` as the runtime extractor dependency. Unit tests use
fixtures and mocks instead of making real YouTube or network calls.

Smoke-test the current CLI:

```bash
ytcap --help
ytcap --version
```

## Installation Target

The long-term installation target is:

```bash
pipx install ytcap
```

Expected usage:

```bash
ytcap --help
```

```bash
ytcap video --url "https://www.youtube.com/watch?v=VIDEO_ID" --lang en --source any
```

## License

This project is planned for release under the MIT License. See `LICENSE.md` for details.
