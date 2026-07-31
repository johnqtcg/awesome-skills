# Format Selection Guide

Advanced format selection patterns for yt-dlp. Use this reference when the user needs specific quality, codec, or container requirements.

## Format Selectors Overview

The `-f` flag accepts a format selection expression. Key operators:

| Operator | Meaning | Example |
|----------|---------|---------|
| `+` | Merge two streams | `bv+ba` (best video + best audio) |
| `/` | Fallback | `bv*+ba/b` (try merge, fall back to best single) |
| `,` | Download multiple | `bv*+ba,ba` (video+audio AND audio-only) |
| `[]` | Filter by property | `bv[height<=1080]` |
| `*` | Include already-merged | `bv*` (includes streams with both video+audio) |

## Common Format Selection Patterns

### Best quality (default)
```bash
-f "bv*+ba/b" --merge-output-format mp4
```

### Resolution cap
```bash
-f "bv*[height<=1080]+ba/b[height<=1080]"
-f "bv*[height<=720]+ba/b[height<=720]"
-f "bv*[height<=480]+ba/b[height<=480]"
```

### Specific codec
```bash
-f "bv[vcodec~='^(h264|avc)'][height<=1080]+ba[acodec~='^(mp4a|aac)']"
```

### Smallest file
```bash
-f "wv*+wa/w" --merge-output-format mp4
```

### VP9/AV1 preference (YouTube)
```bash
-f "bv[vcodec^=av01]+ba/bv[vcodec^=vp9]+ba/bv+ba"
```

## Format Sorting (`-S`)

The `-S` flag provides a more intuitive alternative to complex `-f` expressions:

```bash
# Prefer h264, max 1080p, prefer mp4a audio
-S "res:1080,vcodec:h264,acodec:mp4a"

# Best quality overall
-S "quality"

# Smallest file size
-S "+size"

# Prefer HDR
-S "hdr"
```

### Format sorting fields

| Field | Description |
|-------|-------------|
| `res` | Resolution (e.g., `res:1080` = max 1080p) |
| `vcodec` | Video codec preference |
| `acodec` | Audio codec preference |
| `fps` | Frame rate |
| `hdr` | HDR format preference |
| `size` | File size (prefix `+` for ascending) |
| `br` | Bitrate |
| `asr` | Audio sample rate |
| `quality` | Overall quality score |

**When to use `-S` vs `-f`**:

- `-S` (`--format-sort`) changes *which format counts as "best"*. Every field is a
  **preference**, never a filter. `-S "res:1080"` means "rank 1080p highest"; when
  nothing at or below 1080p exists it still downloads — picking the smallest format
  **above** 1080p. It cannot express a cap.
- `-f` with a bracket filter is the only hard constraint: `bv*[height<=1080]` will
  not select 1440p, and yt-dlp reports "Requested format is not available" instead.
- Combining them is a preference on top of a constraint, not "hard filter + soft sort"
  unless the `-f` itself constrains the same dimension:

```bash
# WRONG — `-S res:1080` is not a cap; a 1440p-only video downloads at 1440p
-f "bv*+ba/b" -S "res:1080,vcodec:h264"

# RIGHT — the cap lives in -f; -S only orders what survives it
-f "bv*[height<=1080]+ba/b[height<=1080]" -S "vcodec:h264"
```

The same distinction applies to codecs: `-S "vcodec:h264"` prefers H.264 and silently
accepts AV1 when no H.264 exists, while `bv*[vcodec^=avc1]` refuses. See
`scenario-templates.md § 1b` for the constrained form.

## Probing Formats

Always probe before using format IDs or complex selectors:

```bash
# List all available formats
yt-dlp -F "<url>"

# Show format with metadata
yt-dlp -F --print "%(id)s %(format)s %(vcodec)s %(acodec)s %(filesize_approx)s" "<url>"
```

Format IDs are **video-specific**, not universal. Never hardcode them.

## Container Considerations

| Container | Pros | Cons |
|-----------|------|------|
| mp4 | Universal compatibility | Requires ffmpeg for merging |
| mkv | Supports all codecs/subs | Some players don't support it |
| webm | YouTube native | Limited player support |

Use `--merge-output-format mp4` for maximum compatibility.
Use `--merge-output-format mkv` when the source uses VP9/AV1 + Opus (avoids transcoding).

## Output Template Variables

Common variables for `-o` templates:

| Variable | Description |
|----------|-------------|
| `%(title)s` | Video title |
| `%(id)s` | Video ID |
| `%(ext)s` | File extension |
| `%(uploader)s` | Uploader name |
| `%(upload_date)s` | Upload date (YYYYMMDD) |
| `%(duration)s` | Duration in seconds |
| `%(view_count)s` | View count |
| `%(playlist_title)s` | Playlist name |
| `%(playlist_index)s` | Playlist position |
| `%(chapter)s` | Chapter name |
| `%(chapter_number)s` | Chapter number |

**Truncation**: `%(title).200s` limits to 200 characters (prevents filesystem errors).
