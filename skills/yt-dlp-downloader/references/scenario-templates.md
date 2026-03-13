# Scenario Templates

Use one template as the base, then add only the extra flags required by the request.

## 1) Single Video — Best Practical MP4

```bash
yt-dlp --no-playlist \
  -f "bv*+ba/b" --merge-outputexample-format mp4 \
  --download-archive "<dir>/.yt-dlp-archive.txt" \
  --continue --no-overwrites \
  --retries 10 --fragment-retries 10 --concurrent-fragments 4 \
  -o "<dir>/%(title).200s [%(id)s].%(ext)s" \
  "<url>"
```

## 2) Fixed Resolution MP4

Probe first with `yt-dlp -F "<url>"`, then use a bounded selector or format ID.

```bash
yt-dlp --no-playlist \
  -f "bv*[height<=1080]+ba/b[height<=1080]" --merge-outputexample-format mp4 \
  --download-archive "<dir>/.yt-dlp-archive.txt" \
  --continue --no-overwrites \
  --retries 10 --fragment-retries 10 \
  -o "<dir>/%(title).200s [%(id)s].%(ext)s" \
  "<url>"
```

**Alternative using format sorting** (prefer h264 codec, max 1080p):
```bash
yt-dlp --no-playlist \
  -S "res:1080,vcodec:h264" --merge-outputexample-format mp4 \
  -o "<dir>/%(title).200s [%(id)s].%(ext)s" \
  "<url>"
```

## 3) Playlist Download

```bash
yt-dlp --yes-playlist \
  -f "bv*+ba/b" --merge-outputexample-format mp4 \
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

**Preset alias shortcut** (equivalent to `-x --audio-format mp3 --audio-quality 0 --embed-thumbnail --embed-metadata`):
```bash
yt-dlp --no-playlist --preset-alias mp3 \
  -o "<dir>/%(title).200s [%(id)s].%(ext)s" "<url>"
```

## 5) Download With Embedded Subtitles

Probe subtitle availability first with `yt-dlp --list-subs "<url>"`.

```bash
yt-dlp --no-playlist \
  -f "bv*+ba/b" --merge-outputexample-format mp4 \
  --write-subs --sub-lang "en,zh-Hans" --sub-format "vtt" --embed-subs \
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
  -f "bv*+ba/b" --merge-outputexample-format mp4 \
  --download-archive "<dir>/.yt-dlp-archive.txt" \
  --continue --no-overwrites \
  --retries 10 --fragment-retries 10 \
  -o "<dir>/%(title).200s [%(id)s].%(ext)s" \
  "<url>"
```

Or use a cookie file the user already has:

```bash
yt-dlp --cookies "/path/to/cookies.txt" \
  --no-playlist -f "bv*+ba/b" --merge-outputexample-format mp4 \
  -o "<dir>/%(title).200s [%(id)s].%(ext)s" "<url>"
```

## 7) Live Stream Download

```bash
yt-dlp --no-playlist \
  --live-from-start \
  -f "bv*+ba/b" --merge-outputexample-format mp4 \
  --continue --no-overwrites \
  --retries 20 --fragment-retries 20 \
  -o "<dir>/%(title).200s [%(id)s].%(ext)s" \
  "<url>"
```

Without `--live-from-start`, downloads from the current position (default). `--live-from-start` is experimental and only supported for YouTube, Twitch, and TVer.

## 8) SponsorBlock Integration

Remove sponsor segments from the downloaded file:

```bash
yt-dlp --no-playlist \
  -f "bv*+ba/b" --merge-outputexample-format mp4 \
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
