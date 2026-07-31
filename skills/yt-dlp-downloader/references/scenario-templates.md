# Scenario Templates

Use one template as the base, then add only the extra flags required by the request.

## 1) Single Video — Best Quality, MP4 Container When Possible

`bv*+ba/b` picks the best streams by quality, not by codec, so the result may be
VP9 or AV1 video and Opus audio remuxed into MP4. That plays everywhere modern
but is **not** guaranteed to be the maximally compatible H.264/AAC MP4. Two
further caveats: `--merge-output-format` applies only when two streams are
merged, so the `/b` fallback can still yield WebM; and if a codec cannot be
remuxed into MP4, yt-dlp keeps the original container rather than failing.

For "must be MP4/H.264" use template 1b. For "best quality, any container" this
template is correct as written.

```bash
yt-dlp --no-playlist \
  -f "bv*+ba/b" --merge-output-format mp4 \
  --download-archive "<dir>/.yt-dlp-archive.txt" \
  --continue --no-overwrites \
  --retries 10 --fragment-retries 10 --concurrent-fragments 4 \
  -o "<dir>/%(title).200s [%(id)s].%(ext)s" \
  "<url>"
```

## 1b) Single Video — Maximum Compatibility (H.264 + AAC, MP4)

Use when the file must play on older TVs, editors, or phones. The selector
constrains the codecs in **both** branches. `[ext=mp4]` alone is not a codec
guarantee — an MP4 container happily holds AV1 or HEVC video and Opus or FLAC
audio — so the fallback repeats the codec filters. If no branch matches, yt-dlp
reports "Requested format is not available"; say that instead of silently
returning a VP9/AV1 file.

Note `bv`, not `bv*`. Per yt-dlp's README, `bv*+ba` merges audio only if the
selected format does not already have an audio stream — it does not append a
second track. The reason to use `bv` here is narrower: `bv*[vcodec^=avc1]` can
match an already-muxed AVC format whose **audio** codec is unconstrained, so the
`ba[acodec^=mp4a]` half never applies and the AAC guarantee is lost. `bv` selects
a video-only stream, which forces the audio constraint to be honoured.

```bash
yt-dlp --no-playlist \
  -f "bv[vcodec^=avc1]+ba[acodec^=mp4a]/b[ext=mp4][vcodec^=avc1][acodec^=mp4a]" \
  --merge-output-format mp4 \
  --download-archive "<dir>/.yt-dlp-archive.txt" \
  --continue --no-overwrites \
  --retries 10 --fragment-retries 10 --concurrent-fragments 4 \
  -o "<dir>/%(title).200s [%(id)s].%(ext)s" \
  "<url>"
```

Verify with `yt-dlp -F "<url>"` that an `avc1` video and an `mp4a` audio stream
exist before promising this. `-S "vcodec:h264,acodec:aac"` only *prefers* them;
the bracket filter above is what makes it a constraint.

## 2) Fixed Resolution MP4

Probe first with `yt-dlp -F "<url>"`, then use a bounded selector or format ID.

```bash
yt-dlp --no-playlist \
  -f "bv*[height<=1080]+ba/b[height<=1080]" --merge-output-format mp4 \
  --download-archive "<dir>/.yt-dlp-archive.txt" \
  --continue --no-overwrites \
  --retries 10 --fragment-retries 10 \
  -o "<dir>/%(title).200s [%(id)s].%(ext)s" \
  "<url>"
```

**Alternative using format sorting** (prefer h264 codec, max 1080p):
```bash
yt-dlp --no-playlist \
  -S "res:1080,vcodec:h264" --merge-output-format mp4 \
  -o "<dir>/%(title).200s [%(id)s].%(ext)s" \
  "<url>"
```

## 3) Playlist Download

```bash
yt-dlp --yes-playlist \
  -f "bv*+ba/b" --merge-output-format mp4 \
  --download-archive "<dir>/.yt-dlp-archive.txt" \
  --continue --no-overwrites \
  --retries 10 --fragment-retries 10 --concurrent-fragments 4 \
  -o "<dir>/%(playlist_title).120s/%(playlist_index)05d - %(title).200s [%(id)s].%(ext)s" \
  "<playlist_url>"
```

## 4) Audio Extraction

```bash
yt-dlp --no-playlist \
  -x --audio-format mp3 --audio-quality 0 \
  --embed-metadata --embed-thumbnail \
  --download-archive "<dir>/.yt-dlp-archive.txt" \
  --continue --no-overwrites \
  --retries 10 --fragment-retries 10 \
  -o "<dir>/%(title).200s [%(id)s].%(ext)s" \
  "<url>"
```

**Preset alias shortcut.** `--preset-alias mp3` expands to exactly:

```
-f 'ba[acodec^=mp3]/ba/b' -x --audio-format mp3
```

That is **all** it does — no `--audio-quality 0`, no `--embed-thumbnail`, no
`--embed-metadata`. Add those explicitly if you want them (the template above
does). Run `yt-dlp --help` and read the "Preset Aliases" section to confirm for
your installed build; yt-dlp may adjust preset contents between releases.
```bash
yt-dlp --no-playlist --preset-alias mp3 \
  --audio-quality 0 --embed-thumbnail --embed-metadata \
  --download-archive "<dir>/.yt-dlp-archive.txt" \
  --continue --no-overwrites \
  --retries 10 --fragment-retries 10 \
  -o "<dir>/%(title).200s [%(id)s].%(ext)s" \
  "<url>"
```

The alias replaces only the format selector and the two extraction flags. The
skill's defaults (archive, continue, no-overwrites, retries, output template)
and the metadata/thumbnail flags are not part of it and must still be appended.

## 5) Download With Embedded Subtitles

Probe subtitle availability first with `yt-dlp --list-subs "<url>"`.

```bash
yt-dlp --no-playlist \
  -f "bv*+ba/b" --merge-output-format mp4 \
  --write-subs --sub-langs "en,zh-Hans" --sub-format "vtt" --embed-subs \
  --download-archive "<dir>/.yt-dlp-archive.txt" \
  --continue --no-overwrites \
  --retries 10 --fragment-retries 10 \
  -o "<dir>/%(title).200s [%(id)s].%(ext)s" \
  "<url>"
```

## 6) Authenticated Download

Prefer browser cookies if available:

```bash
yt-dlp --cookies-from-browser chrome \
  --no-playlist \
  -f "bv*+ba/b" --merge-output-format mp4 \
  --download-archive "<dir>/.yt-dlp-archive.txt" \
  --continue --no-overwrites \
  --retries 10 --fragment-retries 10 \
  -o "<dir>/%(title).200s [%(id)s].%(ext)s" \
  "<url>"
```

Or use a cookie file the user already has:

```bash
yt-dlp --cookies "/path/to/cookies.txt" \
  --no-playlist -f "bv*+ba/b" --merge-output-format mp4 \
  -o "<dir>/%(title).200s [%(id)s].%(ext)s" "<url>"
```

## 7) Live Stream Download

```bash
yt-dlp --no-playlist \
  --live-from-start \
  -f "bv*+ba/b" --merge-output-format mp4 \
  --download-archive "<dir>/.yt-dlp-archive.txt" \
  --continue --no-overwrites \
  --retries 20 --fragment-retries 20 \
  -o "<dir>/%(title).200s [%(id)s].%(ext)s" \
  "<url>"
```

Without `--live-from-start`, downloads from the current position (default). `--live-from-start` is experimental and supported on a small, changing set of
sites — YouTube, Twitch, TVer and mellow-fan as of yt-dlp 2026.07. Read the
current list from `yt-dlp --help` rather than trusting this line; support tables
for fast-moving software go stale between releases.

**Scheduled stream / premiere overlay.** Only when the stream has *not started
yet*, append:

```bash
--wait-for-video 30-120
```

`MIN[-MAX]` is the number of seconds to wait **between retries**, not a total
deadline — yt-dlp will keep polling indefinitely. There is no built-in overall
timeout, so wrap it in the caller's own bound if one is needed. Do not add this
to a stream that is already live: it changes nothing and hides a genuine
"video unavailable" behind an endless retry loop.

## 8) SponsorBlock Integration

Remove sponsor segments from the downloaded file:

```bash
yt-dlp --no-playlist \
  -f "bv*+ba/b" --merge-output-format mp4 \
  --sponsorblock-remove sponsor,selfpromo,interaction \
  --download-archive "<dir>/.yt-dlp-archive.txt" \
  --continue --no-overwrites \
  --retries 10 --fragment-retries 10 \
  -o "<dir>/%(title).200s [%(id)s].%(ext)s" \
  "<url>"
```

Mark sponsor segments as chapters (non-destructive):

```bash
--sponsorblock-mark sponsor,selfpromo
```

SponsorBlock categories: `sponsor`, `intro`, `outro`, `selfpromo`, `preview`, `filler`, `interaction`, `music_offtopic`, `poi_highlight`, `chapter`, `all`.

## 9) Metadata / Probe Only

```bash
yt-dlp --simulate --skip-download "<url>"
yt-dlp -F "<url>"
yt-dlp --list-subs "<url>"
yt-dlp --flat-playlist --print "%(playlist_index)s %(title)s" "<url>"
```

## 10) Optional Flags — Append As Needed

```bash
--restrict-filenames              # Safe filenames for strict filesystems
--no-mtime                        # Don't set file modification time to upload date
--sleep-requests 1                # Delay between requests (rate limit avoidance)
--limit-rate 2M                   # Bandwidth cap
--proxy "http://host:port"        # HTTP/HTTPS/SOCKS proxy
--impersonate chrome              # Browser TLS fingerprint impersonation
--split-chapters                  # Split video by chapters into separate files
--embed-chapters                  # Embed chapter markers in the container
--embed-metadata                  # Embed video metadata
--embed-thumbnail                 # Embed thumbnail image
--write-info-json                 # Save metadata as JSON sidecar
```
