# ytcap

`ytcap` is a Python CLI project for extracting **video metadata** and **subtitle files** from YouTube video, batch, and playlist sources, then turning them into reusable JSON and JSONL outputs.

It is designed for workflows where you have YouTube video URLs, video IDs, or playlists and want structured metadata plus subtitles for search, indexing, dataset preparation, education, or analysis.

## Project Status

This repository is in an early planning and implementation stage. The first target release is:

```text
0.1.0
```

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

### List Available Subtitles

```bash
ytcap inspect --url "https://www.youtube.com/watch?v=VIDEO_ID" --list-subs
```

### Process a Batch File

```bash
ytcap batch --input videos.txt --lang en --source any --format srt --resume --skip-existing --out ./data
```

This command is a later release target.

## Planned Output Layout

```text
data/
  videos/
    VIDEO_ID.info.json
  subtitles/
    VIDEO_ID.en.srt
  normalized/
    VIDEO_ID.en.jsonl
  runs/
    RUN_ID.manifest.json
  failed/
    failed.jsonl
```

## Documentation

| File | Purpose |
|---|---|
| `USAGE.md` | Usage boundaries, limitations, and responsible use notes |
| `CLI_REFERENCE.md` | Planned commands, flags, behavior, and error codes |
| `OUTPUT_FORMAT.md` | Target JSON and JSONL output formats |
| `RELEASE.md` | Packaging and release process |
| `CONTRIBUTING.md` | Contributor expectations |
| `SECURITY.md` | Security policy and sensitive data rules |

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
