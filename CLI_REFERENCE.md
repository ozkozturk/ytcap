# CLI Reference

This document defines the planned `ytcap` CLI commands, flags, behavior rules, and error cases.

Current implementation status:

- `inspect` uses the `yt-dlp` adapter to emit metadata and subtitle availability summaries.
- `video` processes one video and writes normalized metadata plus selected subtitles.
- `export` converts existing SRT/VTT subtitle files to cue-level or sentence-level JSONL.
- Subtitle source selection for normalized tracks is implemented and tested.
- Subtitle format validation for `srt` and `vtt` is implemented and tested.
- Standard output directory layout creation, metadata JSON writing, and selected
  subtitle file download for `video --out` are implemented and tested.
- SRT/VTT cue parsers, cue-level JSONL writer helpers, and basic
  sentence-level segmentation helpers are implemented and tested.
- `batch` is registered as a placeholder and returns a `NOT_IMPLEMENTED` error.

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
- Source selection requires an exact `--lang` match and the requested `--format`
  to be available on the selected track.
- Non-dry-run `video` creates `videos/`, `subtitles/`, `normalized/`, `runs/`,
  and `failed/` under `--out`.
- Metadata JSON is written to `videos/{video_id}.info.json` unless
  `--subs-only` is used.
- Subtitle files are written to
  `subtitles/{video_id}.{lang}.{source}.{format}` unless `--metadata-only` is
  used.
- Existing metadata or subtitle outputs are not overwritten by default; use
  `--overwrite` to replace them or `--skip-existing` to leave them unchanged.
- If a requested subtitle track is not available, the command returns
  `SUBTITLE_NOT_FOUND`.
- `--dry-run` writes no files and avoids metadata/subtitle extraction.

## 5. `export` Command

Status: implemented for existing SRT/VTT file or directory inputs.

Purpose:

- Convert existing subtitle files into JSONL output.
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

Rules:

- `--input` may be one `.srt`/`.vtt` file or one directory.
- Directory input is non-recursive and processes supported files sorted by path.
- Unsupported files inside a directory are ignored.
- A single unsupported file input returns `INVALID_INPUT`.
- Directory input with no supported subtitle files returns `INVALID_INPUT`.
- Output files are written as `{video_id}.{lang}.{segments}.jsonl` under
  `--out`.
- Existing output files are not overwritten by default.
- The command validates target output paths and parses all selected subtitle
  files before writing any JSONL, so duplicate target names, existing outputs,
  or parse errors fail without partial writes.
- `video_id`, language, and source are inferred from file names such as
  `VIDEO_ID.en.manual.srt`.
- `manual` and `auto` source markers are recognized case-insensitively.
- If the file name omits source, JSONL records use `source` value `unknown`.
- `--video-id` and `--lang` overrides are valid only for a single file input.
- Directory input requires each subtitle file to provide at least
  `VIDEO_ID.lang` in its file name.

`cue` segments:

- Each subtitle time range becomes one record.

`sentence` segments:

- Text is split into sentences.
- Initial splitting uses `.`, `?`, and `!` punctuation.
- Timing is matched with simple heuristics and marked with `cue_exact`,
  `cue_merge`, `heuristic`, or `unknown`.
- Advanced NLP packages are not used.

## 6. `batch` Command

Status: post-MVP target. The current CLI registers this command as a placeholder and returns `NOT_IMPLEMENTED`.

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

## 7. `playlist` Command

Status: post-MVP target.

Purpose:

- Process videos inside a playlist URL or ID.

Target usage:

```bash
ytcap playlist --url "https://www.youtube.com/playlist?list=PLAYLIST_ID" --limit 50 --lang en --source any --out ./data
```

Options:

| Flag | Description |
|---|---|
| `--url` | Playlist URL |
| `--id` | Playlist ID |
| `--limit` | Maximum number of videos to process |
| `--start` | Start index |
| `--end` | End index |
| `--lang` | Subtitle language |
| `--source` | `manual`, `auto`, `any` |
| `--format` | `srt`, `vtt` |
| `--out` | Output directory |

## 8. Exit Code Policy

| Exit code | Meaning |
|---|---|
| `0` | Success |
| `1` | General error |
| `2` | User input or flag error |
| `3` | Extractor or `yt-dlp` error |
| `4` | Subtitle not found |
| `5` | File write error |

## 9. Error Message Format

Human-readable format:

```text
error: subtitle not found for language 'en' and source 'manual'
code: SUBTITLE_NOT_FOUND
```

JSON format, when needed:

```json
{
  "ok": false,
  "error": {
    "code": "SUBTITLE_NOT_FOUND",
    "message": "subtitle not found for language 'en' and source 'manual'",
    "details": {
      "language": "en",
      "source": "manual"
    }
  }
}
```

## 10. Conflicting Flag Rules

| Combination | Behavior |
|---|---|
| `--verbose` + `--quiet` | Error |
| `--url` + `--id` | Error |
| `--skip-existing` + `--overwrite` | Error |
| `--metadata-only` + `--subs-only` | Error |
| Invalid `--source` | Error |
| Invalid `--format` | Error |

## 11. Dry Run Behavior

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
