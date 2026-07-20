# Output Format

This document defines the target JSON and JSONL data model produced by `ytcap`.

## 1. Design Principles

The data model follows these principles:

- Raw extractor output and normalized output should remain separate.
- User-facing JSON fields should be stable.
- Missing data should be represented with `null` where possible.
- Subtitle source must be explicit: `manual`, `auto`, or `unknown`.
- Time fields should be stored as numeric seconds.
- File path and format information should be retained so original output context is not lost.

## 2. Metadata JSON

Target file path:

```text
data/videos/{video_id}.info.json
```

Example:

```json
{
  "schema_version": "0.1",
  "video": {
    "id": "abc123",
    "url": "https://www.youtube.com/watch?v=abc123",
    "webpage_url": "https://www.youtube.com/watch?v=abc123",
    "title": "Example Video",
    "description": "Example description",
    "duration_seconds": 320,
    "duration_text": "5:20",
    "upload_date": "20260101",
    "timestamp": 1767225600
  },
  "channel": {
    "id": "channel123",
    "name": "Example Channel",
    "url": "https://www.youtube.com/channel/channel123"
  },
  "media": {
    "availability": "public",
    "live_status": "not_live",
    "thumbnail": "https://example.com/thumb.jpg",
    "tags": ["example", "video"]
  },
  "subtitles": [
    {
      "language": "en",
      "source": "manual",
      "formats": ["srt", "vtt"],
      "selected": true,
      "downloaded": true,
      "path": "data/subtitles/abc123.en.manual.srt"
    },
    {
      "language": "en",
      "source": "auto",
      "formats": ["vtt"],
      "selected": false,
      "downloaded": false,
      "path": null
    }
  ],
  "extraction": {
    "tool": "ytcap",
    "extractor": "yt-dlp",
    "fetched_at": "2026-07-06T20:00:00Z",
    "status": "ok",
    "warnings": []
  }
}
```

## 3. Field Descriptions

### `schema_version`

The output schema version.

Initial version:

```json
"schema_version": "0.1"
```

This field must be updated when the schema changes in a backward-incompatible way.

### `video`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | YouTube video ID |
| `url` | string | Yes | Normalized video URL |
| `webpage_url` | string/null | No | Page URL returned by the extractor |
| `title` | string/null | No | Video title |
| `description` | string/null | No | Video description |
| `duration_seconds` | number/null | No | Video duration in seconds |
| `duration_text` | string/null | No | Human-readable duration |
| `upload_date` | string/null | No | Date format returned by the extractor |
| `timestamp` | number/null | No | Unix timestamp |

### `channel`

| Field | Type | Description |
|---|---|---|
| `id` | string/null | Channel ID |
| `name` | string/null | Channel name |
| `url` | string/null | Channel URL |

### `media`

| Field | Type | Description |
|---|---|---|
| `availability` | string/null | Availability such as `public`, `unlisted`, `private`, or `unknown` |
| `live_status` | string/null | Status such as `live`, `upcoming`, `not_live`, or `unknown` |
| `thumbnail` | string/null | Selected thumbnail URL |
| `tags` | array | Tags, or an empty list when unavailable |

### `subtitles`

Each item describes one subtitle track.

| Field | Type | Description |
|---|---|---|
| `language` | string | Language code |
| `source` | string | `manual`, `auto`, or `unknown` |
| `formats` | array | Available formats |
| `selected` | boolean | Whether this track was selected in the current run |
| `downloaded` | boolean | Whether it was written to a file |
| `path` | string/null | Output file path |

### `extraction`

| Field | Type | Description |
|---|---|---|
| `tool` | string | `ytcap` |
| `extractor` | string | `yt-dlp` |
| `fetched_at` | string | UTC ISO timestamp |
| `status` | string | `ok`, `partial`, or `failed` |
| `warnings` | array | Warnings |

## 4. Subtitle Cue Model

Internal cue model after SRT/VTT parsing:

```json
{
  "index": 1,
  "start": 12.4,
  "end": 16.8,
  "text": "This is an example sentence."
}
```

Fields:

| Field | Type | Description |
|---|---|---|
| `index` | number/null | Subtitle block index |
| `start` | number | Start time in seconds |
| `end` | number | End time in seconds |
| `text` | string | Cleaned subtitle text |

## 5. Cue-Level JSONL

Target file path:

```text
data/normalized/{video_id}.{lang}.cue.jsonl
```

Each line is one JSON object:

```json
{"schema_version":"0.1","type":"cue","video_id":"abc123","language":"en","source":"manual","start":12.4,"end":16.8,"text":"This is an example sentence.","normalized_text":"this is an example sentence","cue_index":1,"channel_id":"channel123","channel_name":"Example Channel","channel_url":"https://www.youtube.com/channel/channel123","video_title":"Example Video","video_url":"https://www.youtube.com/watch?v=abc123","video_webpage_url":"https://www.youtube.com/watch?v=abc123","video_duration_seconds":320,"video_upload_date":"20260101","available_manual_subtitles":["tr"],"downloaded_subtitles":["tr"],"dataset_category":"education","category_source":"user"}
```

Fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Schema version |
| `type` | string | `cue` |
| `video_id` | string | Video ID |
| `language` | string | Language code |
| `source` | string | `manual`, `auto`, or `unknown` |
| `start` | number | Start time in seconds |
| `end` | number | End time in seconds |
| `text` | string | Cue text |
| `normalized_text` | string | Search-friendly normalized cue text |
| `cue_index` | number/null | Original cue index |

Cue records also include the common JSONL enrichment fields listed below.

## 6. Sentence-Level JSONL

Target file path:

```text
data/normalized/{video_id}.{lang}.sentence.jsonl
```

Example line:

```json
{"schema_version":"0.1","type":"sentence","video_id":"abc123","language":"en","source":"manual","start":12.4,"end":18.2,"text":"This is an example sentence.","normalized_text":"this is an example sentence","sentence_index":1,"timing_strategy":"heuristic","cue_coverage":"single","timing_precision":"estimated_end","playback_start":12.15,"playback_end":18.6,"start_cue_index":7,"end_cue_index":7,"cue_count":1,"start_char_in_first_cue":0,"end_char_in_last_cue":28,"boundary_engine":"punctuation-v2","channel_id":"channel123","channel_name":"Example Channel","channel_url":"https://www.youtube.com/channel/channel123","video_title":"Example Video","video_url":"https://www.youtube.com/watch?v=abc123","video_webpage_url":"https://www.youtube.com/watch?v=abc123","video_duration_seconds":320,"video_upload_date":"20260101","available_manual_subtitles":["tr"],"downloaded_subtitles":["tr"],"dataset_category":"education","category_source":"user"}
```

Note:

Sentence boundaries are a textual estimate. Cue text is joined into one
timeline, sentence character spans are detected with a dependency-free
punctuation rule engine, and those spans are mapped back to cue timing.

- Cue-aligned boundaries use the source cue's own start/end time.
- Cue-internal boundaries are approximated with weighted token
  interpolation: words and punctuation receive approximate speaking-time
  weights, and the boundary is placed proportionally inside the cue.
- `playback_start` and `playback_end` add a small safety padding (about
  0.25 s before and 0.40 s after) around the estimated sentence range for
  clip playback. `playback_start` is clamped at `0`; `playback_end` is not
  clipped because the video duration is unknown at segmentation time.
- This is not word-level forced alignment; no audio analysis is performed.

Fields:

| Field | Type | Description |
|---|---|---|
| `cue_coverage` | string | `single` when the sentence touches one cue, `multiple` otherwise |
| `timing_precision` | string | How `start`/`end` were derived; see values below |
| `playback_start` | number | Padded playback start in seconds |
| `playback_end` | number | Padded playback end in seconds |
| `start_cue_index` | number/null | Index of the first source cue the sentence touches |
| `end_cue_index` | number/null | Index of the last source cue the sentence touches |
| `cue_count` | number | How many source cues the sentence touches |
| `start_char_in_first_cue` | number | Character offset of the sentence start inside the first cue's normalized text |
| `end_char_in_last_cue` | number | Character offset of the sentence end inside the last cue's normalized text |
| `boundary_engine` | string | Sentence boundary detector version, e.g. `punctuation-v2` |

Possible `timing_precision` values:

| Value | Description |
|---|---|
| `cue_aligned` | Both boundaries match source cue start/end times |
| `estimated_start` | The sentence starts inside its first cue |
| `estimated_end` | The sentence ends inside its last cue |
| `estimated_both` | Both boundaries fall inside their boundary cues |
| `unknown` | The sentence has no terminal punctuation; timing quality is uncertain |

The legacy `timing_strategy` field is kept for backward compatibility and is
derived from the fields above:

| `timing_strategy` | Derivation |
|---|---|
| `cue_exact` | `cue_coverage=single` and `timing_precision=cue_aligned` |
| `cue_merge` | `cue_coverage=multiple` |
| `heuristic` | `cue_coverage=single` with an estimated boundary |
| `unknown` | `timing_precision=unknown` |

Sentence records also include the common JSONL enrichment fields listed below.

### Sentence Artifact Manifest

Every sentence JSONL export is published with a required companion manifest:

```text
data/normalized/{video_id}.{lang}.sentence.manifest.json
```

The JSONL and manifest are staged as sibling temporary files, validated, and
then published as a pair. An export failure does not leave an incomplete final
pair. JSONL serialization is deterministic UTF-8: record order and object key
order are stable, separators are compact, every record ends with LF (`\n`), and
rows contain no timestamps, random identifiers, or host paths.

Example manifest:

```json
{
  "schema_version": "0.1",
  "artifact_type": "sentence_jsonl",
  "producer": {"name": "ytcap", "version": "0.3.0"},
  "identity": {"video_id": "abc123", "language": "en", "source": "manual"},
  "segmentation": {
    "boundary_engine": "punctuation-v2",
    "timing_estimator": "weighted-token-v1",
    "time_quantum_decimals": 3
  },
  "playback_hint": {
    "start_padding_seconds": 0.25,
    "end_padding_seconds": 0.4
  },
  "input": {
    "filename": "../subtitles/abc123.en.manual.srt",
    "format": "srt",
    "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  },
  "output": {
    "filename": "abc123.en.sentence.jsonl",
    "sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
    "record_count": 123,
    "schema_version": "0.1"
  },
  "metadata": {
    "filename": "../videos/abc123.info.json",
    "sha256": "123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0"
  },
  "quality_summary": {
    "cue_aligned": 100,
    "estimated_start": 8,
    "estimated_end": 10,
    "estimated_both": 5,
    "unknown": 0,
    "empty_text": 0,
    "non_positive_duration": 0,
    "overlap_with_previous": 0,
    "large_gap": 1,
    "long_duration": 0
  }
}
```

Normative field rules:

| Field | Required | Description |
|---|---|---|
| `schema_version` | Yes | Manifest schema version, currently `0.1` |
| `artifact_type` | Yes | Always `sentence_jsonl` |
| `producer` | Yes | Producer name and exact installed ytcap package version |
| `identity` | Yes | Non-empty video ID/language and `manual`, `auto`, or `unknown` source |
| `segmentation` | Yes | Boundary engine, timing estimator, and timestamp quantization versions |
| `playback_hint` | Yes | Padding used for playback hints; exact sentence times remain in JSONL |
| `input` | Yes | Logical/relative source filename, SRT/VTT format, and exact-byte SHA-256 |
| `output` | Yes | Logical JSONL filename, exact-byte SHA-256, record count, and row schema version |
| `metadata` | Yes | Logical metadata filename/hash, or two `null` values when unavailable |
| `quality_summary` | Yes | Timing-precision counts and suspicious-record counts; records are reported, not discarded |

Manifest `schema_version` evolves independently from the sentence-row schema.
The manifest is new at version `0.1`; sentence JSONL remains at `0.1` because
this change preserves every existing row field and adds no incompatible row
meaning. Future manifest-only additions change the manifest version according
to compatibility, without automatically changing JSONL rows.

## 7. Common JSONL Enrichment Fields

The `export` command enriches cue-level and sentence-level JSONL records from
the matching normalized metadata file when it is available:

```text
data/videos/{video_id}.info.json
```

Missing metadata files and missing fields inside metadata JSON are represented
by the existing enrichment fields with `null` values. Video ID, language,
source, timing, sentence index, and text always come from the subtitle artifact
and filename/CLI identity; display metadata is never used to invent identity.

| Field | Type | Description |
|---|---|---|
| `normalized_text` | string | Search-friendly text derived from the record's display `text` |
| `channel_id` | string/null | Channel ID from metadata |
| `channel_name` | string/null | Channel name from metadata |
| `channel_url` | string/null | Channel URL from metadata |
| `video_title` | string/null | Video title from metadata |
| `video_url` | string/null | Normalized video URL from metadata |
| `video_webpage_url` | string/null | Extractor webpage URL from metadata |
| `video_duration_seconds` | number/null | Video duration in seconds from metadata |
| `video_upload_date` | string/null | Upload date from metadata |
| `available_manual_subtitles` | array/null | Non-English manual subtitle languages available in metadata |
| `downloaded_subtitles` | array/null | Non-English subtitle languages marked downloaded in metadata |
| `dataset_category` | string/null | User-provided dataset category from `--category` |
| `category_source` | string | `user` when `--category` is provided, otherwise `none` |

`normalized_text` is intended for simple text search. It is computed from the
record's `text` by Unicode normalizing, casefolding/lowercasing, removing
apostrophe-like characters, converting other punctuation to spaces, and
collapsing whitespace. For example, `I can't wait;` becomes `i cant wait`.

Subtitle language arrays exclude English language codes:

```text
en
en-*
```

When `--category` is omitted, `dataset_category` is `null` and
`category_source` is `none`.

## 8. Run Manifest Model

Batch, playlist, or channel processing should keep a manifest for each run.

Target file path:

```text
data/runs/{run_id}.manifest.json
```

Example:

```json
{
  "schema_version": "0.1",
  "run_id": "2026-07-06T20-00-00Z",
  "started_at": "2026-07-06T20:00:00Z",
  "finished_at": "2026-07-06T20:10:00Z",
  "command": "batch",
  "input": {
    "type": "file",
    "path": "videos.txt"
  },
  "options": {
    "language": "en",
    "source": "any",
    "format": "srt",
    "skip_existing": true
  },
  "summary": {
    "total": 100,
    "ok": 90,
    "skipped": 5,
    "failed": 5
  },
  "outputs": [
    "data/videos/abc123.info.json"
  ],
  "errors": [
    {
      "video_id": "def456",
      "code": "SUBTITLE_NOT_FOUND",
      "message": "subtitle not found"
    }
  ]
}
```

## 9. Failed JSONL Model

File path:

```text
data/failed/failed.jsonl
```

Example line:

```json
{"schema_version":"0.1","video_id":"def456","url":"https://www.youtube.com/watch?v=def456","code":"SUBTITLE_NOT_FOUND","message":"subtitle not found","failed_at":"2026-07-06T20:05:00Z"}
```

## 10. Backward Compatibility

Schemas may change during `0.x` releases. Each schema change should be tracked in:

- `OUTPUT_FORMAT.md`
- `CHANGELOG.md`
- Relevant test fixtures

After `1.0.0`, backward-incompatible schema changes require a major version increase.
