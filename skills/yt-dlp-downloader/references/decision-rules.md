# Decision Rules

Use this file when choosing the final command. State the choice and why.

## 1) `best` vs Explicit Format

Use the default selector when the user only wants "best quality" or "best MP4":

- `-f "bv*+ba/b" --merge-output-format mp4`

Probe with `-F` first when:

- the user wants a specific resolution, codec, HDR profile, or format ID
- the site frequently changes available formats
- the user reports `Requested format is not available`

## 2) Format ID vs Bounded Selector vs Format Sorting

**Use a format ID** when:
- the user already chose an exact row from `yt-dlp -F`
- the site exposes unusual mappings where a bounded selector is unreliable

**Use a bounded selector** (`-f "bv*[height<=1080]"`) when:
- the user wants "up to 1080p" or similar hard constraints
- portability matters more than a single exact stream ID

**Use format sorting** (`-S "res:1080,vcodec:h264"`) when:
- the user expresses a preference rather than a hard constraint
- multiple quality/codec preferences need to be balanced
- combining with `-f` for hard filter + soft sort

See `references/format-selection-guide.md` for detailed `-S` usage.

## 3) Probe First

Probe first when:

- URL authenticity is uncertain
- playlist scope is unclear
- auth may be required
- subtitle availability matters
- specific format/resolution requested

Skip the probe only for simple, public, single-video downloads where the user already accepted default best quality.

## 4) Playlist Behavior

Use `--no-playlist` by default for a single watch URL unless the user explicitly wants the whole playlist.

Use `--yes-playlist` when:

- the user says playlist, channel batch, or course series
- the URL is clearly a playlist and the user wants all entries

Use `--flat-playlist` first when the playlist may be very large or the user wants to inspect titles before downloading.

## 5) Subtitles

Use `--list-subs` before finalizing subtitle flags when availability is unknown.

**Embed subtitles** (`--embed-subs`) when:
- the user wants a single self-contained media file
- the container supports it (mp4, mkv)

**Keep subtitles separate** (`--write-subs` without `--embed-subs`) when:
- editing or external subtitle workflows are likely
- the container or player compatibility is uncertain

**Auto-generated subtitles**: Use `--write-auto-subs` when the user wants YouTube's auto-generated captions. Note these are lower quality than human-created subtitles.

## 6) Audio Extraction

Use `-x --audio-format mp3 --audio-quality 0` when the user clearly wants an audio deliverable.

**Preset alias alternative**: `--preset-alias mp3` is equivalent to `-x --audio-format mp3 --audio-quality 0 --embed-thumbnail --embed-metadata`.

Do not extract audio when the user only wants to preserve the original media and may later need video.

## 7) Cookies

Use `--cookies-from-browser <browser>` when:
- the user is on the same machine with an authenticated browser session
- the site requires login or age verification
- supported browsers: chrome, firefox, opera, edge, brave, vivaldi, safari

Use `--cookies /path/to/cookies.txt` when:
- the user already has a cookie file
- browser extraction is unavailable

Do not recommend cookies unless auth is plausibly required.

## 8) Output Template

Use a flat template for one-off downloads:

- `%(title).200s [%(id)s].%(ext)s`

Use a nested template for playlists:

- `%(playlist_title).120s/%(playlist_index)05d - %(title).200s [%(id)s].%(ext)s`

Add `--restrict-filenames` when the target filesystem is strict or cross-platform portability matters.

## 9) SponsorBlock

Use `--sponsorblock-remove` when the user wants segments physically removed from the file.

Use `--sponsorblock-mark` when the user wants non-destructive chapter markers instead.

**Category selection by user intent:**

- "skip sponsors" / "remove sponsors" → `sponsor,selfpromo,interaction` (conservative — keeps intros, outros, filler)
- "skip ALL sponsor segments" / "remove everything" / "no ads at all" → `all` (aggressive — includes intro, outro, filler, preview, music_offtopic, poi_highlight)

Default to the conservative set unless the user's phrasing clearly implies removing all categories.

## 10) Live Streams

Use `--live-from-start` for ongoing live streams when the user wants the complete recording from the beginning. This is experimental (YouTube, Twitch, TVer only).

Default behavior (without `--live-from-start`) records from the current position.

Use `--wait-for-video 30` for scheduled premieres/streams that haven't started yet.

## 11) Browser Impersonation

Use `--impersonate chrome` when a site blocks yt-dlp's default User-Agent or uses TLS fingerprinting. Requires `curl_cffi` package.

Do not use impersonation by default — only when downloads fail with 403 or the site is known to require it.
