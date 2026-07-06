# Usage and Limitations

This document explains the intended use, responsible use notes, and technical limitations of `ytcap`.

## 1. Intended Use

`ytcap` is designed for:

- Extracting metadata and subtitles from your own working lists.
- Preparing transcript datasets for education and analysis.
- Creating local data for search or indexing systems.
- Inspecting video metadata and subtitle availability.

## 2. Out-of-Scope Use

This tool is not designed for:

- Redistributing copyrighted content without permission.
- Bypassing platform access restrictions.
- Trying to access restricted or non-public content.
- Downloading video or audio files.
- Bypassing YouTube API terms.

## 3. Subtitle Quality

Subtitle sources can vary in quality:

| Source | Description |
|---|---|
| `manual` | Human-provided subtitles, usually higher quality |
| `auto` | Automatic speech recognition output, which may contain errors |
| `unknown` | Source could not be determined with confidence |

JSON output must always include the subtitle source.

## 4. Missing Metadata

Because the official YouTube Data API is not used, some metadata fields may not always be available.

Missing fields should be represented with:

- `null`
- Empty lists
- Warnings

## 5. Missing Subtitles

Not every video has subtitles.

In that case:

- The single-video command should return a controlled error.
- Batch and playlist commands should add the affected video to the failed output and continue.
- If `--fail-fast` is provided, processing may stop at the first error.

## 6. Network and Extractor Fragility

Changes on YouTube or network issues can affect extractor behavior.

For that reason:

- Unit tests should not use the network.
- Errors should be reported with clear codes.
- The `yt-dlp` version may need to be updated when extractor behavior changes.

## 7. Large Batch Runs

Large batch or playlist runs can involve:

- Long runtimes
- Rate-limit-like errors
- Temporary network failures
- Removed videos
- Videos without subtitles

To manage these, the following options are supported:

- `--resume`
- `--skip-existing`
- `--max-errors`
- `--fail-fast`

## 8. Data Storage

Users are responsible for the data they download or generate.

Do not commit the following to the repository:

- Large real subtitle archives
- Extensive transcripts copied from copyrighted content
- Personal or restricted video lists
- Cookie or session files

## 9. Technical Limitations

Initial limitations:

- No advanced NLP sentence segmentation.
- Output is focused on JSON and JSONL.
- No SQLite or database import support.

These limitations are intentional design choices.
