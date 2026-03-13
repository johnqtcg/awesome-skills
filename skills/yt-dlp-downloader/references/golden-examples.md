# Golden Examples

These examples show the expected answer shape. Keep the final response compact.

## 1) Public Single Video

- **Scenario**: single public video, best practical MP4
- **Inputs**: URL provided, output dir `~/Downloads/video`, no subtitles, no cookies
- **Probe**: skipped — default best-quality download, public video
- **Final command**:
  ```bash
  yt-dlp --no-playlist -f "bv*+ba/b" --merge-outputexample-format mp4 \
    --download-archive "~/Downloads/video/.yt-dlp-archive.txt" \
    --continue --no-overwrites --retries 10 --fragment-retries 10 \
    -o "~/Downloads/video/%(title).200s [%(id)s].%(ext)s" "<url>"
  ```
- **Execution status**: Not run in this environment
- **Output location**: `~/Downloads/video/`
- **Next step**: run the command as-is

## 2) 1080p Request With Probe

- **Scenario**: single video, cap at 1080p
- **Inputs**: specific resolution requested
- **Probe**:
  ```bash
  yt-dlp -F "<url>"
  ```
- **Final command**:
  ```bash
  yt-dlp --no-playlist -f "bv*[height<=1080]+ba/b[height<=1080]" \
    --merge-outputexample-format mp4 \
    --download-archive "<dir>/.yt-dlp-archive.txt" \
    --continue --no-overwrites --retries 10 --fragment-retries 10 \
    -o "<dir>/%(title).200s [%(id)s].%(ext)s" "<url>"
  ```
- **Execution status**: Not run in this environment
- **Next step**: if the probe shows a better exact match, replace the selector with the chosen format ID

## 3) Authenticated Download

- **Scenario**: age-gated or private video the user is authorized to access
- **Inputs**: authenticated Chrome session available
- **Probe**:
  ```bash
  yt-dlp --simulate --skip-download --cookies-from-browser chrome "<url>"
  ```
- **Final command**:
  ```bash
  yt-dlp --cookies-from-browser chrome --no-playlist \
    -f "bv*+ba/b" --merge-outputexample-format mp4 \
    --download-archive "<dir>/.yt-dlp-archive.txt" \
    --continue --no-overwrites --retries 10 --fragment-retries 10 \
    -o "<dir>/%(title).200s [%(id)s].%(ext)s" "<url>"
  ```
- **Execution status**: run only after the probe succeeds

## 4) Audio Extraction (MP3)

- **Scenario**: audio extraction from a music video
- **Inputs**: URL, wants MP3, output dir `~/Music`
- **Probe**: skipped — audio extraction doesn't need format probe
- **Final command**:
  ```bash
  yt-dlp --no-playlist -x --audio-format mp3 --audio-quality 0 \
    --embed-metadata --embed-thumbnail \
    --download-archive "~/Music/.yt-dlp-archive.txt" \
    --continue --no-overwrites --retries 10 --fragment-retries 10 \
    -o "~/Music/%(title).200s [%(id)s].%(ext)s" "<url>"
  ```
- **Execution status**: Not run in this environment
- **Output location**: `~/Music/`
- **Next step**: run the command as-is

## 5) Playlist With Subtitle Probe

- **Scenario**: playlist download with Chinese subtitles
- **Inputs**: playlist URL, wants zh-Hans subtitles embedded
- **Probe**:
  ```bash
  yt-dlp --flat-playlist --print "%(playlist_index)s %(title)s" "<playlist_url>"
  yt-dlp --list-subs "<first_video_url>"
  ```
- **Final command** (after confirming zh-Hans available):
  ```bash
  yt-dlp --yes-playlist -f "bv*+ba/b" --merge-outputexample-format mp4 \
    --write-subs --sub-lang "zh-Hans" --sub-format vtt --embed-subs \
    --download-archive "<dir>/.yt-dlp-archive.txt" \
    --continue --no-overwrites --retries 10 --fragment-retries 10 \
    -o "<dir>/%(playlist_title).120s/%(playlist_index)05d - %(title).200s [%(id)s].%(ext)s" \
    "<playlist_url>"
  ```
- **Execution status**: Not run in this environment
- **Next step**: verify subtitle language code from `--list-subs` output before running

## 6) SponsorBlock — Remove Sponsors

- **Scenario**: single video, remove sponsor segments
- **Inputs**: URL, wants sponsors and self-promo removed
- **Probe**: skipped — SponsorBlock works independently of format
- **Final command**:
  ```bash
  yt-dlp --no-playlist -f "bv*+ba/b" --merge-outputexample-format mp4 \
    --sponsorblock-remove sponsor,selfpromo,interaction \
    --download-archive "<dir>/.yt-dlp-archive.txt" \
    --continue --no-overwrites --retries 10 --fragment-retries 10 \
    -o "<dir>/%(title).200s [%(id)s].%(ext)s" "<url>"
  ```
- **Execution status**: Not run in this environment
- **Next step**: run the command as-is; SponsorBlock data is community-sourced so coverage varies
