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
{"schema_version":"0.1","type":"cue","video_id":"abc123","language":"en","source":"manual","start":12.4,"end":16.8,"text":"This is an example sentence.","normalized_text":"this is an example sentence","cue_index":1,"channel_id":"channel123","channel_name":"Example Channel","channel_url":"https://www.youtube.com/channel/channel123","video_title":"Example Video","video_url":"https://www.youtube.com/watch?v=abc123","video_webpage_url":"https://www.youtube.com/watch?v=abc123","video_duration_seconds":320,"video_upload_date":"20260101","available_manual_subtitles":["tr"],"downloaded_subtitles":["tr"]}
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
{"schema_version":"0.1","type":"sentence","video_id":"abc123","language":"en","source":"manual","start":12.4,"end":18.2,"text":"This is an example sentence.","normalized_text":"this is an example sentence","sentence_index":1,"timing_strategy":"heuristic","channel_id":"channel123","channel_name":"Example Channel","channel_url":"https://www.youtube.com/channel/channel123","video_title":"Example Video","video_url":"https://www.youtube.com/watch?v=abc123","video_webpage_url":"https://www.youtube.com/watch?v=abc123","video_duration_seconds":320,"video_upload_date":"20260101","available_manual_subtitles":["tr"],"downloaded_subtitles":["tr"]}
```

Note:

Sentence-level timing may not always be exact. A sentence can span multiple
cues, or multiple sentences can share a single cue. The initial implementation
uses a punctuation-based split on `.`, `?`, and `!`, then maps sentence spans
back to cue timing with simple heuristics.

Possible `timing_strategy` values:

```text
cue_exact
cue_merge
heuristic
unknown
```

Meaning:

| Value | Description |
|---|---|
| `cue_exact` | One complete sentence maps to one complete subtitle cue |
| `cue_merge` | One sentence spans more than one subtitle cue |
| `heuristic` | A sentence occupies part of a cue, so timing is estimated |
| `unknown` | The sentence boundary or timing quality is uncertain |

Sentence records also include the common JSONL enrichment fields listed below.

## 7. Common JSONL Enrichment Fields

The `export` command enriches cue-level and sentence-level JSONL records from
the matching normalized metadata file:

```text
data/videos/{video_id}.info.json
```

Missing fields inside that metadata JSON are represented as `null`.

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

`normalized_text` is intended for simple text search. It is computed from the
record's `text` by Unicode normalizing, casefolding/lowercasing, removing
apostrophe-like characters, converting other punctuation to spaces, and
collapsing whitespace. For example, `I can't wait;` becomes `i cant wait`.

Subtitle language arrays exclude English language codes:

```text
en
en-*
```

## 8. Run Manifest Model

Batch or playlist processing should keep a manifest for each run.

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
