# yt-dlp Anti-Examples (Extended)

Read this file when reviewing or generating yt-dlp commands. Each example shows a common mistake and the correct alternative.

For the three most critical mistakes (guessing formats, missing `--no-playlist`, and claiming success without execution), see SKILL.md directly.

## 2. Using `--cookies` to bypass content the user is not authorized to access

Cookies are for authenticated access, not circumvention. Never describe cookies as a way to bypass paywalls, DRM, or geographic restrictions on copyrighted content.

## 4. Hardcoding format IDs across different videos

Format IDs are video-specific, not universal constants. A format ID that works for one video may not exist for another.

```
BAD:  yt-dlp -f 137+140 "<url1>" && yt-dlp -f 137+140 "<url2>"
GOOD: yt-dlp -F "<url>"  →  pick the correct ID per video
```

## 6. Skipping `ffmpeg` dependency check before merge/extract operations

`--merge-output-format mp4` and `-x` silently fail or produce degraded output without ffmpeg. Always verify `ffmpeg -version` before commands that require it.

## 7. Recommending `--write-subs` without checking subtitle availability

Probe with `--list-subs` first to avoid empty output.

```
BAD:  yt-dlp --write-subs --sub-lang ja "<url>"  (hoping Japanese subs exist)
GOOD: yt-dlp --list-subs "<url>"  →  confirm "ja" exists  →  then add --write-subs
```

## 8. Ignoring `--download-archive` for repeatable batch downloads

Without `--download-archive`, re-running the same command downloads everything again. Always include it for playlists and batch operations.
