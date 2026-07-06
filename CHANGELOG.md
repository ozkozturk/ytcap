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
- Added a `batch` placeholder that returns a clear not-implemented error.
- Added a `yt-dlp` subprocess adapter with controlled extractor errors.
- Added normalized video metadata mapping and inspect summary output.
- Added tested subtitle source selection for `manual`, `auto`, and `any`.
- Added controlled subtitle format validation for `srt` and `vtt`.
- Added standard output directory layout helpers and `video --out` directory creation.
- Added `video` metadata JSON writing and selected SRT/VTT subtitle file download.

### Changed

- Nothing yet.

### Fixed

- Nothing yet.

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
