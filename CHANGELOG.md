# Changelog

This file tracks user-facing changes between project releases.

The format follows the spirit of "Keep a Changelog".

## [Unreleased]

### Added

- Planned the initial public documentation set.
- Defined the project purpose, core decisions, CLI goals, output model, and dependency expectations.
- Added the initial Python package scaffold.
- Added the basic `ytcap` console entry point with `--help` and `--version`.
- Added parser and validation skeletons for `inspect`, `video`, and `export`.
- Added a `yt-dlp` subprocess adapter with controlled extractor errors.
- Added normalized video metadata mapping and inspect summary output.
- Added tested subtitle source selection for `manual`, `auto`, and `any`.
- Added controlled subtitle format validation for `srt` and `vtt`.
- Added standard output directory layout helpers and `video --out` directory creation.
- Added `video` metadata JSON writing and selected SRT/VTT subtitle file download.
- Added SRT/VTT cue parser helpers and a cue-level JSONL writer.
- Added basic punctuation-based sentence segmentation and sentence-level JSONL writer helpers.
- Added `export` command wiring for existing SRT/VTT files to cue-level or sentence-level JSONL.
- Added `batch` input parser service to read video URLs or IDs from text files with comment support.
- Added `batch` command for processing multiple video URLs or IDs from a text file, tracking execution metrics, and writing run manifests.
- Added `failed_writer` helper for logging failed video processing attempts to `failed/failed.jsonl`.
- Added `--resume` and `--skip-existing` support to the `batch` command for interrupted and incremental runs.
- Added `playlist` command to process YouTube playlists using `yt-dlp` playlist flat extraction.
- Added `--limit`, `--start`, and `--end` range controls to the `playlist` command.
- Added run manifest generation, `--resume`, `--skip-existing`, `--fail-fast`, `--max-errors`, and `--dry-run` support to the `playlist` command.
- Added JSON error output for controlled `inspect --json` errors.
- Added a `ytcap[dev]` extra with release build and package-check tooling.


### Changed

- Updated `batch --resume` so previous failures are retried and the run
  manifest reflects the latest final state.
- Updated package license metadata to the current SPDX `license` and
  `license-files` form.

### Fixed

- Prevented `export` from partially writing JSONL when duplicate target paths, existing outputs, or later parse errors are detected.
- Prevented `batch --dry-run` from creating output directories.
- Rejected non-positive `batch --max-errors` values with `INVALID_INPUT`.
- Made playlist flat extraction handle bare video IDs and malformed playlist entries more defensively.
- Made batch and playlist `--skip-existing` match the requested subtitle language, source, and format.
- Made playlist `--resume` ignore unrelated batch manifests and playlist manifests with different URLs or range/output options.

### Removed

- Nothing yet.

## [0.1.0] - TBD

Initial target release.

Planned scope:

- Python package scaffold.
- `ytcap --help`.
- `ytcap --version`.
- `inspect` command.
- Single-video metadata extraction.
- Single-video subtitle extraction.
- JSON metadata output.
- SRT/VTT subtitle output.
- Cue-level JSONL export.
- Basic unit test suite.
