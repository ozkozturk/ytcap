# CLI Reference

This document defines the planned `ytcap` CLI commands, flags, behavior rules, and error cases.

Current implementation status:

- `inspect` uses the `yt-dlp` adapter to emit metadata and subtitle availability summaries.
- The adapter requires `yt-dlp>=2026.06.09` and rejects older runtime versions.
- `video` processes one video and writes normalized metadata plus selected subtitles.
- `export` converts existing SRT/VTT subtitle files to enriched cue-level or sentence-level JSONL.
- Subtitle source selection for normalized tracks is implemented and tested.
- Subtitle format validation for `srt` and `vtt` is implemented and tested.
- Standard output directory layout creation, metadata JSON writing, and selected
  subtitle file download for `video --out` are implemented and tested.
- SRT/VTT cue parsers, cue-level JSONL writer helpers, and basic
  sentence-level segmentation helpers are implemented and tested.
- `batch` processes text files of video URLs or IDs, writes run manifests, logs
  failures, and supports `--resume`, `--skip-existing`, and `--dry-run`.
- `playlist` processes YouTube playlists by extracting video entries through
  `yt-dlp`, with `--limit`, `--start`, and `--end` range controls.
  Supports `--resume` or `--skip-existing`, `--fail-fast`, `--max-errors`,
  and `--dry-run`.
- `channel` processes YouTube channels by extracting video entries through
  `yt-dlp`, with range controls, `--ignore-no-subs` filtering, and standard run rules.
- Dynamic output filename parts are validated before paths are built, so user
  input or extractor metadata cannot escape the selected output directories.

## 1. General Command Shape

```bash
ytcap <command> [options]
```

Global options:

| Flag | Description |
|---|---|
| `--help` | Show help output |
| `--version` | Show the installed version |
| `--verbose` | Emit more detailed logs |
| `--quiet` | Emit minimal output |
| `--no-color` | Disable colored output when color support exists |

Colored output is not required at the start. `--no-color` only becomes meaningful once colored output is added.

## 2. Input Rules

Video sources may be provided in either form:

```bash
--url "https://www.youtube.com/watch?v=VIDEO_ID"
```

or:

```bash
--id "VIDEO_ID"
```

Rules:

- `--url` and `--id` must not be used together.
- If one of them is required, omitting both must return an error.
- URL parsing should be as tolerant as reasonably possible.
- The normalized video ID should be used in output file names.

Error categories:

```text
CONFLICTING_FLAGS
INVALID_INPUT
```

## 3. `inspect` Command

Status: implemented for metadata and subtitle availability summaries through the `yt-dlp` adapter.

Purpose:

- Give quick information about a video.
- Show whether metadata can be extracted.
- List subtitle languages and sources.
- Write no files.

Usage:

```bash
ytcap inspect --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

```bash
ytcap inspect --id "VIDEO_ID"
```

Options:

| Flag | Description | Example |
|---|---|---|
| `--url` | Video URL | `--url "..."` |
| `--id` | Video ID | `--id "abc123"` |
| `--list-subs` | List subtitles in detail | `--list-subs` |
| `--json` | Emit inspect output as JSON | `--json` |

Expected human-readable output example:

```text
Video
  ID: abc123
  Title: Example Video
  Duration: 320s

Subtitles
  en: manual, auto
  tr: auto
```

Expected JSON output example:

```json
{
  "video_id": "abc123",
  "title": "Example Video",
  "duration_seconds": 320,
  "subtitles": [
    {"language": "en", "source": "manual", "formats": ["srt", "vtt"]},
    {"language": "en", "source": "auto", "formats": ["vtt"]}
  ]
}
```

## 4. `video` Command

Status: implemented for single-video metadata JSON writing and selected SRT/VTT
subtitle file download through the `yt-dlp` adapter. JSONL normalization is a
later milestone.

Purpose:

- Process one video.
- Produce metadata JSON.
- Download subtitles when requested.
- Create the output directory structure.

Usage:

```bash
ytcap video --url "https://www.youtube.com/watch?v=VIDEO_ID" --lang en --source any --format srt --out ./data
```

Options:

| Flag | Description | Default |
|---|---|---|
| `--url` | Video URL | None |
| `--id` | Video ID | None |
| `--lang` | Subtitle language | `en` |
| `--source` | Subtitle source: `manual`, `auto`, `any` | `any` |
| `--format` | Subtitle format: `srt`, `vtt` | `srt` |
| `--out` | Output directory | `./data` |
| `--metadata-only` | Write only metadata | Off |
| `--subs-only` | Write only subtitles | Off |
| `--skip-existing` | Skip existing output | Off |
| `--overwrite` | Rewrite existing output | Off |
| `--dry-run` | Show planned work without writing files | Off |

Rules:

- `--skip-existing` and `--overwrite` cannot be used together.
- `--metadata-only` and `--subs-only` cannot be used together.
- `--source manual` must not fall back to automatic subtitles.
- `--source auto` must not use manual subtitles.
- `--source any` should try manual subtitles first, then automatic subtitles.
- `--format` accepts `srt` or `vtt`; other values return `UNSUPPORTED_FORMAT`.
- Source selection requires the requested `--format` to be available on the
  selected track. Language matching is exact except that `--lang en` also
  accepts English subtitle tracks reported as `en-*`, such as `en-GB` or
  `en-eEY6OEpapP`.
- Non-dry-run `video` creates `videos/`, `subtitles/`, `normalized/`, `runs/`,
  and `failed/` under `--out`.
- Metadata JSON is written to `videos/{video_id}.info.json` unless
  `--subs-only` is used.
- Subtitle files are written to
  `subtitles/{video_id}.{lang}.{source}.{format}` unless `--metadata-only` is
  used. The `{lang}` path component is the requested CLI language, so an
  accepted `en-*` English track still writes to `...en.manual.srt` for
  `--lang en --source manual --format srt`.
- Dynamic filename parts such as video ID, language, source, format, segment
  type, and run ID must be non-empty single filename components; path
  separators, absolute paths, control characters, `.` and `..` are rejected.
- Existing metadata or subtitle outputs are not overwritten by default; use
  `--overwrite` to replace them or `--skip-existing` to leave them unchanged.
- Metadata is written after subtitle selection and download succeed. If a
  requested subtitle is unavailable, no new partial metadata file is left
  behind unless `--metadata-only` was requested.
- With `--skip-existing`, a complete matching metadata+subtitle pair skips the
  video. If existing metadata is stale or incomplete but the subtitle can be
  completed, metadata is refreshed after the subtitle step succeeds.
- `--skip-existing` uses the same English variant matching as subtitle
  selection, so a selected `en-*` manual track satisfies a later `--lang en`
  request.
- If a requested subtitle track is not available, the command returns
  `SUBTITLE_NOT_FOUND`.
- `--dry-run` writes no files and avoids metadata/subtitle extraction.

## 5. `export` Command

Status: implemented for existing SRT/VTT file or directory inputs.

Purpose:

- Convert existing subtitle files into JSONL output.
- Enrich each JSONL row with normalized search text and matching video metadata.
- Perform no downloads.

Usage:

```bash
ytcap export --input ./data/subtitles --segments cue --format jsonl --out ./data/normalized
```

Options:

| Flag | Description | Default |
|---|---|---|
| `--input` | SRT/VTT file or directory | Required |
| `--segments` | `cue` or `sentence` | `cue` |
| `--format` | Output format | `jsonl` |
| `--out` | Output directory | `./data/normalized` |
| `--video-id` | Video ID override for a single file | Optional |
| `--lang` | Language override | Optional |
| `--category` | Dataset category value for JSONL records | Optional |

Rules:

- `--input` may be one `.srt`/`.vtt` file or one directory.
- Directory input is non-recursive and processes supported files sorted by path.
- Unsupported files inside a directory are ignored.
- A single unsupported file input returns `INVALID_INPUT`.
- Directory input with no supported subtitle files returns `INVALID_INPUT`.
- Output files are written as `{video_id}.{lang}.{segments}.jsonl` under
  `--out`.
- A matching normalized metadata file may exist at
  `videos/{video_id}.info.json` in the standard output layout. For a subtitle
  input under `subtitles/`, the sibling `videos/` directory is used. For a
  single file outside `subtitles/`, `--out` should point at the standard
  `normalized/` directory so the sibling `videos/` directory can be found.
- When no standard output layout or metadata sidecar is available, the export
  remains valid and existing enrichment fields are written as `null`.
- Inferred or overridden `video_id` and language values must be safe filename
  parts. Unsafe values return `INVALID_INPUT` before writing any output.
- Existing output files are not overwritten by default.
- The command validates target output paths and parses all selected subtitle
  files before writing any JSONL, so duplicate target names, existing outputs,
  or parse errors fail without partial writes.
- `video_id`, language, and source are inferred from file names such as
  `VIDEO_ID.en.manual.srt`.
- `manual` and `auto` source markers are recognized case-insensitively.
- If the file name omits source, JSONL records use `source` value `unknown`.
- Missing fields inside the metadata JSON are represented as `null`.
- A metadata file that exists but is unreadable or invalid JSON fails before
  any JSONL output is written. A missing metadata file does not fail export.
- Each JSONL record includes `normalized_text`, computed from the record's
  display `text` by lowercasing/casefolding, removing apostrophe-like
  characters, converting punctuation to spaces, and collapsing whitespace.
- Each JSONL record includes compact video and channel metadata plus
  non-English subtitle language arrays. English language codes `en` and `en-*`
  are excluded from `available_manual_subtitles` and `downloaded_subtitles`;
  empty arrays are represented as `null`.
- If `--category` is provided, JSONL records use that value for
  `dataset_category` and set `category_source` to `user`.
- If `--category` is omitted, JSONL records use `dataset_category: null` and
  `category_source: "none"`.
- `--category` must not be empty.
- `--video-id` and `--lang` overrides are valid only for a single file input.
- Directory input requires each subtitle file to provide at least
  `VIDEO_ID.lang` in its file name.

`cue` segments:

- Each subtitle time range becomes one record.

`sentence` segments:

- Text is split into sentences with a dependency-free punctuation rule
  engine that handles common abbreviations (`Dr.`, `e.g.`, `etc.`),
  decimals and versions (`3.14`, `v2.4.1`), domains and technical names
  (`example.com`, `Node.js`), initials (`J. R. R. Tolkien`, `U.S.`), and
  keeps closing quotes/brackets inside the sentence.
- Cue gaps act only as an auxiliary signal: a strong gap (over 0.6 s) can
  split text without terminal punctuation when the next cue starts with an
  uppercase letter, but a well punctuated continuing sentence is never
  split because of a gap.
- Cue-internal boundaries are approximated with weighted token
  interpolation; cue-aligned boundaries keep the source cue's own time.
- Each record carries `cue_coverage`, `timing_precision`, padded
  `playback_start`/`playback_end`, and cue provenance fields
  (`start_cue_index`, `end_cue_index`, `cue_count`,
  `start_char_in_first_cue`, `end_char_in_last_cue`, `boundary_engine`).
- The legacy `timing_strategy` field (`cue_exact`, `cue_merge`,
  `heuristic`, `unknown`) is derived from those fields.
- Sentence exports also write
  `{video_id}.{lang}.sentence.manifest.json`. JSONL and manifest are validated
  and atomically published as a pair. The manifest records logical paths,
  source/output/metadata SHA-256 values, producer and engine versions, record
  count, identity, and quality counts.
- Advanced NLP packages and audio analysis are not used.

### 5.1 `verify` Command

Status: implemented for sentence artifact manifests.

```bash
ytcap verify --manifest ./data/normalized/VIDEO_ID.en.sentence.manifest.json
```

The command verifies JSONL hash and record count, identity consistency, row
types and schema version, monotonic sentence indices, finite exact/playback
timestamps, normalized text, boundary engine, and quality-summary counts. It
also verifies source and metadata hashes when those referenced relative files
are present.

## 6. `batch` Command

Status: implemented.

Purpose:

- Process a file containing video URLs or IDs.

Target usage:

```bash
ytcap batch --input videos.txt --lang en --source any --format srt --resume --skip-existing --out ./data
```

Options:

| Flag | Description |
|---|---|
| `--input` | File containing URLs or IDs |
| `--lang` | Subtitle language |
| `--source` | `manual`, `auto`, `any` |
| `--format` | `srt`, `vtt` |
| `--resume` | Continue an interrupted run |
| `--skip-existing` | Skip existing outputs |
| `--fail-fast` | Stop at the first error |
| `--max-errors` | Stop after the given number of errors |
| `--out` | Output directory |
| `--dry-run` | Show planned work without writing files |

Rules:

- `--input` must point to a readable text file with at least one URL or ID.
- `--max-errors` must be a positive integer when provided.
- One video error does not stop the batch unless `--fail-fast` is set or
  `--max-errors` is reached.
- `--resume` skips entries already completed in the latest manifest and retries
  previous failures; the new manifest reflects the latest final state.
- `--skip-existing` skips only when the existing metadata points to a downloaded
  subtitle matching the requested `--lang`, `--source`, and `--format`.
  `--source any` accepts either an existing manual or automatic subtitle.
- Failed attempts are appended to `failed/failed.jsonl`.
- `--dry-run` writes no files or directories and avoids metadata/subtitle
  extraction.

### Batch Input File Format

The `--input` file is a plain text file containing one YouTube video URL or video ID per line.
- Empty lines and lines containing only whitespace are ignored.
- Lines starting with `#` (with optional leading whitespace) are ignored as comment lines.
- Inline comments starting with `#` are supported, and the comment text plus any preceding whitespace are ignored.

Example input file:
```text
# This is a comment line
dQw4w9WgXcQ                  # Rick Astley - Never Gonna Give You Up
https://youtu.be/jNQXAC9IVRw # Another video URL
```


## 7. `playlist` Command

Status: implemented.

Purpose:

- Process videos inside a playlist URL or ID.

Usage:

```bash
ytcap playlist --url "https://www.youtube.com/playlist?list=PLAYLIST_ID" --limit 50 --lang en --source any --out ./data
```

Options:

| Flag | Description |
|---|---|
| `--url` | Playlist URL |
| `--id` | Playlist ID |
| `--limit` | Maximum number of videos to process |
| `--start` | Start index (1-based) |
| `--end` | End index (inclusive) |
| `--lang` | Subtitle language |
| `--source` | `manual`, `auto`, `any` |
| `--format` | `srt`, `vtt` |
| `--out` | Output directory |
| `--skip-existing` | Skip already processed videos |
| `--fail-fast` | Stop at the first error |
| `--max-errors` | Stop after the given number of errors |
| `--resume` | Continue an interrupted run |
| `--dry-run` | Show planned work without writing files |

Rules:

- `--url` and `--id` cannot be used together.
- One of `--url` or `--id` is required.
- `--start` is 1-based and must be a positive integer.
- `--end` is inclusive and must be greater than or equal to `--start`.
- `--limit` must be a positive integer when provided.
- Playlist entries are fetched through `yt-dlp --flat-playlist`; the official
  YouTube Data API is not used.
- Range selection applies `--start` and `--end` first, then applies `--limit`.
- `--skip-existing` skips only when the existing metadata points to a downloaded
  subtitle matching the requested `--lang`, `--source`, and `--format`.
  `--source any` accepts either an existing manual or automatic subtitle.
- `--resume` continues only from the latest playlist manifest with the same
  playlist URL and output-affecting options: `--lang`, `--source`, `--format`,
  `--limit`, `--start`, and `--end`.
- `--skip-existing` and `--resume` cannot be used together for `playlist`.
- `--dry-run` writes no files or directories and avoids per-video
  metadata/subtitle extraction.


## 8. `channel` Command

Status: implemented.

Purpose:

- Process videos inside a YouTube channel URL or ID.

Usage:

```bash
ytcap channel --url "https://www.youtube.com/@TED" --limit 50 --lang en --source manual --ignore-no-subs --out ./data
```

Options:

| Flag | Description |
|---|---|
| `--url` | YouTube channel URL |
| `--id` | YouTube channel ID |
| `--limit` | Maximum number of videos to process |
| `--start` | Start index (1-based) |
| `--end` | End index (inclusive) |
| `--lang` | Subtitle language |
| `--source` | `manual`, `auto`, `any` |
| `--format` | `srt`, `vtt` |
| `--out` | Output directory |
| `--skip-existing` | Skip already processed videos |
| `--fail-fast` | Stop at the first error |
| `--max-errors` | Stop after the given number of errors |
| `--resume` | Continue an interrupted run |
| `--dry-run` | Show planned work without writing files |
| `--ignore-no-subs` | Skip videos without the requested subtitle track instead of treating them as failures |

Rules:

- `--url` and `--id` cannot be used together.
- One of `--url` or `--id` is required.
- `--start` is 1-based and must be a positive integer.
- `--end` is inclusive and must be greater than or equal to `--start`.
- `--limit` must be a positive integer when provided.
- Channel URLs are normalized by appending `/videos` if not already targeting a tab (e.g. `https://www.youtube.com/@TED` -> `https://www.youtube.com/@TED/videos`).
- Flat playlist extraction fetches only up to the required limit via `--playlist-end` for massive speed improvement on channels.
- Sub-playlists/folders or nested channel tabs are ignored; only video URL entries are processed.
- `--ignore-no-subs` treats `SUBTITLE_NOT_FOUND` errors as skipped rather than failed.
- Range selection applies `--start` and `--end` first, then applies `--limit`.
- `--skip-existing` skips only when the existing metadata points to a downloaded
  subtitle matching the requested `--lang`, `--source`, and `--format`.
  `--source any` accepts either an existing manual or automatic subtitle.
- `--resume` continues only from the latest channel manifest with the same
  channel URL and output-affecting options: `--lang`, `--source`, `--format`,
  `--limit`, `--start`, `--end`, and `--ignore-no-subs`.
- `--skip-existing` and `--resume` cannot be used together for `channel`.
- `--dry-run` writes no files or directories and avoids per-video
  metadata/subtitle extraction.


## 9. Exit Code Policy

| Exit code | Meaning |
|---|---|
| `0` | Success |
| `1` | General error |
| `2` | User input or flag error |
| `3` | Extractor or `yt-dlp` error |
| `4` | Subtitle not found |
| `5` | File write error |

## 10. Error Message Format

Human-readable format:

```text
error: subtitle not found for language 'en', source 'manual', and format 'srt'
code: SUBTITLE_NOT_FOUND
```

JSON error output is used only for commands that expose JSON output. In the
current CLI, controlled `inspect` errors use this shape when `--json` is
provided; other commands continue to use the human-readable stderr format.

```json
{
  "ok": false,
  "error": {
    "code": "SUBTITLE_NOT_FOUND",
    "message": "subtitle not found for language 'en', source 'manual', and format 'srt'",
    "details": {
      "language": "en",
      "source": "manual",
      "format": "srt"
    }
  }
}
```

## 11. Conflicting Flag Rules

| Combination | Behavior |
|---|---|
| `--verbose` + `--quiet` | Error |
| `--url` + `--id` | Error |
| `--skip-existing` + `--overwrite` | Error |
| `playlist --skip-existing` + `playlist --resume` | Error |
| `channel --skip-existing` + `channel --resume` | Error |
| `--metadata-only` + `--subs-only` | Error |
| Invalid `--source` | Error |
| Invalid `--format` | Error |

## 12. Dry Run Behavior

When `--dry-run` is provided:

- Network calls should be kept to a minimum where possible.
- No files should be written.
- The command should show which files would be written.

Example:

```text
Dry run
  Video: abc123
  Metadata output: data/videos/abc123.info.json
  Subtitle output: data/subtitles/abc123.en.manual.srt
  No files written.
```
