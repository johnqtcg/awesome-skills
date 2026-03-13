# Safety and Recovery

Use this file for auth handling, output-path safety, error recovery, and version management.

## 1) Cookie Safety

- Only use cookies for content the user is authorized to access
- Prefer `--cookies-from-browser` over copying raw cookie contents
- Do not ask the user to paste cookies into chat
- If cookies are required but unavailable, stop at a recommendation and say auth is the blocker
- Supported browsers for `--cookies-from-browser`: chrome, firefox, opera, edge, brave, vivaldi, safari

## 2) Output Safety

- Prefer ASCII output templates with title truncation: `%(title).200s`
- Use `--download-archive` for repeatable runs (prevents re-downloading)
- Use `--no-overwrites` unless the user explicitly wants replacement
- Use `--continue` so partial files can resume
- Use `--restrict-filenames` when portability matters (replaces spaces and special chars)
- Never write to system directories — always use a user-specified or `~/Downloads` path

## 3) Logging

Add shell logging when troubleshooting or running batches:

```bash
2>&1 | tee "<dir>/yt-dlp.log"
```

Use logs when:
- diagnosing 403/429 errors
- downloading large playlists
- handling unstable networks
- debugging format selection issues

## 4) Recovery Patterns

### `HTTP Error 403` — Forbidden

Likely causes: auth required, geo-restriction, or bot detection.

```bash
# Try with cookies
yt-dlp --cookies-from-browser chrome "<url>"

# Try with browser impersonation (requires curl_cffi)
yt-dlp --impersonate chrome "<url>"

# Try with rate limiting
yt-dlp --sleep-requests 1 --limit-rate 2M "<url>"
```

### `HTTP Error 429` — Rate Limited

```bash
yt-dlp --sleep-requests 2 --limit-rate 1M --retries 20 "<url>"
```

### `Requested format is not available`

Re-probe and select from actual availability:

```bash
yt-dlp -F "<url>"
# Then use a format ID or bounded selector from the outputexample
```

### `ffmpeg not found` / Merge failure

```bash
# Verify ffmpeg installation
ffmpeg -version

# Install if missing (macOS)
brew install ffmpeg

# Install if missing (Linux)
sudo apt install ffmpeg
```

### YouTube extraction errors / `Sign in to confirm` / `nsig` errors

Often caused by outdated yt-dlp or missing yt-dlp-ejs:

```bash
# Update yt-dlp to latest
yt-dlp -U

# Or switch to nightly for latest fixes
yt-dlp --update-to nightly

# Install yt-dlp-ejs for full YouTube support
pip install yt-dlp-ejs
```

### Frequent timeout / connection reset

```bash
yt-dlp --retries 20 --fragment-retries 20 --concurrent-fragments 1 "<url>"
```

### Geo-restricted content (user has legal access)

```bash
# Use a proxy
yt-dlp --proxy "socks5://host:port" "<url>"

# Force IPv4 (some sites have IPv6 issues)
yt-dlp --force-ipv4 "<url>"
```

### Large playlist interrupted

Resume safely — `--download-archive` tracks completed items:

```bash
# Re-run the same command; already-downloaded items are skipped
yt-dlp --yes-playlist --download-archive "<dir>/.yt-dlp-archive.txt" ...
```

## 5) Version Management

yt-dlp is updated frequently. Sites change their anti-bot measures, so using the latest version is critical.

```bash
# Check current version
yt-dlp --version

# Update to latest stable
yt-dlp -U

# Switch to nightly (recommended for active users)
yt-dlp --update-to nightly

# Switch to master (bleeding edge, may have regressions)
yt-dlp --update-to master
```

When a download fails unexpectedly, **always try updating first** before debugging further.

## 6) What To Report After Execution

If execution ran, report:

- command used
- whether the download succeeded
- where the file was written
- the key failure line if it failed
- the next corrective command

If execution did not run, report:

- `Not run in this environment`
- one exact command to run next
