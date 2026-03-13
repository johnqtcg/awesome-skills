---
name: yt-dlp-downloader
description: |
  Generate and run yt-dlp download commands with probe-driven format selection, safe output naming, retry defaults, and structured execution reports.
  Use when users want to download videos, extract audio, fetch playlists, grab subtitles, handle authenticated/age-gated content, or download live streams.
  Covers single videos, playlists, audio extraction, subtitle-inclusive downloads, format-ID / resolution-capped downloads, SponsorBlock integration, live streams, and browser-cookie authentication.
allowed-tools: Read, Grep, Glob, Bash
---

# yt-dlp Downloader

Probe-driven download workflow with explicit format selection and safe retry defaults.

## Mandatory Gates

Gates execute in strict serial order. Any gate failure blocks all subsequent steps.

```
1) Scope         2) Dependency    3) Ambiguity     4) Probe
   Classification → Check       → Resolution    → Before Download
   │                │              │               │
   scenario type    yt-dlp+ffmpeg  unclear?        -F / --list-subs
   → classify       → verify      → STOP+ASK      → inspect first
        │                │              │               │
        5) Auth Safety   6) Execution   7) Execution
           Gate        →    Mode      →    Integrity
           │                │              │
           cookies/DRM      full/degraded  actually ran?
           → enforce        → auto-select  → report honestly
```

### 1) Scope Classification Gate

Map every request into exactly one scenario before proceeding:

| Scenario | Trigger |
|----------|---------|
| Single video | One URL, default quality or specific format |
| Fixed resolution | User mentions 720p, 1080p, 4K, or specific codec |
| Playlist | Playlist URL, "all videos", "course", "channel" |
| Audio extraction | "mp3", "audio only", "podcast", "music" |
| Subtitles | "subtitles", "captions", "srt", specific language |
| Authenticated | "private", "members-only", "age-gated", login required |
| Live stream | "live", "stream", "premiere", "currently streaming" |
| SponsorBlock | "skip sponsors", "remove intros", "no ads" |

**Goal**: Determine which scenario template to use from `references/scenario-templates.md`.

**Composite requests**: When multiple scenarios apply (e.g., playlist + resolution cap + subtitles), choose the primary scenario as the template base (typically the delivery mechanism — single video, playlist, or audio extraction), then overlay flags from secondary scenarios. Document the composition in the Output Contract's Scenario field.

### 2) Dependency Gate

Before execution, verify:

```bash
yt-dlp --version
ffmpeg -version
```

**ffmpeg is required** when: merging video+audio (`-f bv*+ba`), embedding subtitles (`--embed-subs`), extracting audio (`-x`), embedding thumbnails (`--embed-thumbnail`), or using `--merge-output-format`.

**yt-dlp-ejs + JS runtime**: Full YouTube support requires `yt-dlp-ejs` and a JavaScript runtime (deno recommended, node/bun/quickjs also work). If YouTube downloads fail with extraction errors, recommend:
```bash
pip install yt-dlp-ejs
# Ensure deno, node, or bun is in PATH
```

If a dependency is missing: state `Not available in this environment`, name the exact missing dependency, and provide the install command.

### 3) Ambiguity Resolution Gate

**STOP and ASK** if:
- URL is not provided
- Output directory is unspecified and matters (batch/playlist)
- Resolution preference is unclear ("good quality" — what resolution?)
- Playlist scope is ambiguous (full playlist vs single video from playlist URL)
- Subtitle language is needed but not specified
- Multiple URLs given without clear batch vs individual intent

### 4) Probe Gate

Do not guess format availability. Run a probe first when any of these apply:

| Condition | Probe Command |
|-----------|--------------|
| Specific resolution/codec/format requested | `yt-dlp -F "<url>"` |
| Subtitle language availability unknown | `yt-dlp --list-subs "<url>"` |
| Playlist scope unclear or very large | `yt-dlp --flat-playlist --print "%(playlist_index)s %(title)s" "<url>"` |
| URL may require auth or redirect | `yt-dlp --simulate --skip-download "<url>"` |
| Site often changes formats | `yt-dlp -F "<url>"` |

**Skip** the probe only for simple, public, single-video downloads where default best quality is acceptable.

### 5) Auth Safety Gate

- Use cookies **only** for content the user is authorized to access
- Prefer `--cookies-from-browser <browser>` over raw cookie files
- **Never** ask the user to paste cookie contents into chat
- **Never** describe cookies as a way to bypass paywalls or DRM
- **Never** help circumvent geographic restrictions on copyrighted content
- If auth is required but unavailable, stop at the command recommendation

### 6) Execution Mode Gate

Auto-select mode based on environment:

| Signal | → Mode |
|--------|--------|
| Shell access available, yt-dlp installed | **Full** |
| Shell available but yt-dlp missing | **Blocked** (install first) |
| No shell access / sandbox environment | **Degraded** |

### 7) Execution Integrity Gate

Never claim a download succeeded unless the command actually ran.

**If executed**: report final command, destination path, success/failure, key stderr/stdout summary.
**If not executed**: report `Not run in this environment`, reason, exact command to run.

## Defaults

Apply these unless the user requests otherwise:

```bash
--download-archive "<dir>/.yt-dlp-archive.txt"
--continue
--no-overwrites
--retries 10 --fragment-retries 10
-o "<dir>/%(title).200s [%(id)s].%(ext)s"
```

Append `2>&1 | tee "<dir>/yt-dlp.log"` when logging is useful (batch, troubleshooting, unstable network).

## Anti-Examples (Core Mistakes)

For the full set of 8 anti-examples, read `references/anti-examples.md`. The three most critical are inlined here:

1. **Guessing format availability without probing** — formats change per site and per video. Probe first.
   ```
   BAD:  yt-dlp -f 137+140 "<url>"  (assuming format IDs exist)
   GOOD: yt-dlp -F "<url>"  →  then pick from actual list
   ```

3. **Omitting `--no-playlist` for single-video watch URLs** — YouTube watch URLs can trigger full playlist download.
   ```
   BAD:  yt-dlp -f "bv*+ba/b" "https://youtube.com/watch?v=xxx&list=yyy"
   GOOD: yt-dlp --no-playlist -f "bv*+ba/b" "https://youtube.com/watch?v=xxx&list=yyy"
   ```

5. **Claiming download success without running the command** — if you did not execute it, say so.

## Honest Degradation

| Level | Condition | Action |
|-------|-----------|--------|
| **Full** | yt-dlp + ffmpeg available, shell access, command executed | Complete execution report with all 7 output fields |
| **Degraded** | No shell access or sandbox environment | Provide recommended command + state assumptions + suggest probe command if confidence is low |
| **Blocked** | yt-dlp not installed, or request involves DRM/unauthorized access | State the blocker + provide install command or explain why the request cannot proceed |

Never report download success, file size, or format availability in Degraded or Blocked mode.

## Safety Rules

1. Never help download content the user is not authorized to access
2. Never describe cookies as a DRM/paywall bypass method
3. Never ask the user to paste cookie contents into chat
4. Never claim a download ran unless it actually executed
5. Never hardcode format IDs without probing the specific video
6. Always include `--no-playlist` for single-video watch URLs with playlist parameters
7. Always verify ffmpeg before merge/extract/embed operations
8. Always pair `--embed-subs` with `--write-subs` (or `--write-auto-subs`) — `--embed-subs` alone does not download subtitles

## Output Contract

Every response must include these 7 fields:

1. **Scenario** — which template was selected
2. **Inputs** — URL, output dir, format preference, subtitle needs, auth method
3. **Probe** — probe command + results summary, or "skipped" with reason
4. **Final command** — one complete, copy-pasteable command
5. **Execution status** — ran successfully / failed (with key error) / not run (with reason)
6. **Output location** — expected file path pattern
7. **Next step** — corrective action if failed, or confirmation if succeeded

## Load References Selectively

| Trigger | Reference | Timing |
|---------|-----------|--------|
| Every task | `references/scenario-templates.md` | Before scenario selection |
| Every task | `references/golden-examples.md` | Before formatting the final answer |
| Choosing between format selectors, playlist modes, or subtitle strategies | `references/decision-rules.md` | Before final command assembly |
| Specific quality/codec/HDR requests | `references/format-selection-guide.md` | Before probe interpretation |
| Auth need, extraction errors, or troubleshooting | `references/safety-and-recovery.md` | Before recovery guidance |
| Reviewing or generating commands | `references/anti-examples.md` | Before quality/self-check |

## Bundled Assets

- Scenario templates: `references/scenario-templates.md`
- Decision rules: `references/decision-rules.md`
- Safety and recovery: `references/safety-and-recovery.md`
- Golden examples: `references/golden-examples.md`
- Format selection guide: `references/format-selection-guide.md`
- Anti-examples (extended): `references/anti-examples.md`
- Contract tests: `scripts/tests/test_skill_contract.py`
- Golden scenario tests: `scripts/tests/test_golden_scenarios.py`
- Regression runner: `scripts/run_regression.sh`
