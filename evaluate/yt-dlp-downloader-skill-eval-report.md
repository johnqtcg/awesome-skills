# yt-dlp-downloader Skill Evaluation Report

> Evaluation framework: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> Evaluation date: 2026-03-12
> Evaluation subject: `yt-dlp-downloader`

---

`yt-dlp-downloader` is a skill for generating and running yt-dlp download commands. It is suited for single videos, playlists, audio extraction, subtitle downloads, SponsorBlock, resolution limits, and authenticated download scenarios. Its three standout strengths are: probe-first, using format lists and subtitle info to decide command combinations instead of guessing parameters; safe defaults including `--no-playlist`, retries, output naming, and archive to reduce accidental full-playlist downloads, re-downloads, and runaway commands; and structured execution reports, especially useful for complex combined requests to reuse, review, and adjust.

## 1. Evaluation Overview

This evaluation reviews the yt-dlp-downloader skill along two axes: **actual task performance** and **token cost-effectiveness**. Three yt-dlp command-generation scenarios of increasing complexity were designed (single video download, audio extraction + subtitles, playlist + resolution + SponsorBlock + subtitles). Each scenario was run with both with-skill and without-skill configurations, for 3 scenarios × 2 configs = 6 independent subagent runs, scored against 40 assertions.

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| **Assertion pass rate** | **40/40 (100%)** | 18/40 (45.0%) | **+55.0 pp** |
| **Output Contract structured report** | 3/3 correct | 0/3 | Skill-only |
| **Probe decision compliance** | 3/3 correct | 0/3 | Skill-only |
| **Safety guard (--no-playlist)** | 3/3 (including correct --yes-playlist in playlist scenario) | 0/2 (missing in single-video scenarios) | Largest safety delta |
| **Safe defaults (archive/retries/truncation)** | 3/3 correct | 0/3 | Skill-only |
| **Skill Token cost (SKILL.md only)** | ~2,370 tokens | 0 | — |
| **Skill Token cost (with references)** | ~5,100–6,260 tokens | 0 | — |
| **Token cost per 1% pass-rate gain** | ~43 tokens (SKILL.md only) / ~103 tokens (full) | — | — |

---

## 2. Test Methodology

### 2.1 Scenario Design

| Scenario | User request | Core focus | Assertions |
|----------|--------------|------------|------------|
| Eval 1: Single video download | "Help me download this YouTube video to ~/Downloads/videos, MP4 format best quality" | Basic command structure, safe defaults, Output Contract | 12 |
| Eval 2: Audio extraction + subtitles | "Extract audio as MP3, save English subtitles as SRT" | Dual-scenario combination, subtitle probing, ffmpeg dependency | 13 |
| Eval 3: Playlist + 720p + SponsorBlock + subtitles | "Download entire playlist at max 720p, skip sponsors, embed Chinese subtitles" | Four scenarios combined, format selection, complex command combination | 15 |

### 2.2 Execution

- With-skill runs first read SKILL.md and its referenced materials
- Without-skill runs read no skill, using model default yt-dlp knowledge
- All runs in Degraded mode (no yt-dlp installed); evaluates command recommendation quality, not actual execution
- 6 subagents run in parallel

---

## 3. Assertion Pass Rate

### 3.1 Overview

| Scenario | Assertions | With Skill | Without Skill | Delta |
|----------|-----------|-----------|--------------|-------|
| Eval 1: Single video download | 12 | **12/12 (100%)** | 5/12 (41.7%) | +58.3% |
| Eval 2: Audio extraction + subtitles | 13 | **13/13 (100%)** | 7/13 (53.8%) | +46.2% |
| Eval 3: Playlist + 720p + SponsorBlock + subtitles | 15 | **15/15 (100%)** | 6/15 (40.0%) | +60.0% |
| **Total** | **40** | **40/40 (100%)** | **18/40 (45.0%)** | **+55.0%** |

### 3.2 Per-Assertion Details

#### Eval 1: Single Video Download

| # | Assertion | With Skill | Without Skill |
|---|-----------|:---------:|:------------:|
| A1 | `--no-playlist` flag present | ✅ | ❌ |
| A2 | Best quality format selector (`bv*+ba/b` or equivalent) | ✅ | ✅ |
| A3 | `--merge-output-format mp4` | ✅ | ✅ |
| A4 | `--download-archive` flag present | ✅ | ❌ |
| A5 | `--retries` and `--fragment-retries` | ✅ | ❌ |
| A6 | Title truncation `%(title).200s` | ✅ | ❌ |
| A7 | 7-field Output Contract complete | ✅ | ❌ |
| A8 | Probe decision correct (skip + reason) | ✅ | ❌ |
| A9 | Output path includes `~/Downloads/videos` | ✅ | ✅ |
| A10 | No hardcoded format ID | ✅ | ✅ |
| A11 | Mentions ffmpeg dependency | ✅ | ✅ |
| A12 | Explicit Degraded mode declaration | ✅ | ❌ |

#### Eval 2: Audio Extraction + Subtitles

| # | Assertion | With Skill | Without Skill |
|---|-----------|:---------:|:------------:|
| B1 | `-x` flag present | ✅ | ✅ |
| B2 | `--audio-format mp3` | ✅ | ✅ |
| B3 | `--audio-quality 0` (best VBR quality) | ✅ | ❌ |
| B4 | Subtitle probe `--list-subs` recommended | ✅ | ❌ |
| B5 | `--write-subs` (standalone file, not embed) | ✅ | ✅ |
| B6 | `--sub-lang en` or equivalent | ✅ | ✅ |
| B7 | `--convert-subs srt` (ensure SRT output) | ✅ | ✅ |
| B8 | Mentions ffmpeg dependency | ✅ | ✅ |
| B9 | 7-field Output Contract complete | ✅ | ❌ |
| B10 | `--no-playlist` present | ✅ | ❌ |
| B11 | Output directory `~/Music/podcast/` | ✅ | ✅ |
| B12 | `--download-archive` present | ✅ | ❌ |
| B13 | Title truncation `%(title).200s` | ✅ | ❌ |

#### Eval 3: Playlist + 720p + SponsorBlock + Subtitles

| # | Assertion | With Skill | Without Skill |
|---|-----------|:---------:|:------------:|
| C1 | `--yes-playlist` explicitly declared | ✅ | ❌ |
| C2 | Resolution cap `[height<=720]` or `-S "res:720"` | ✅ | ✅ |
| C3 | `--sponsorblock-remove` with relevant categories | ✅ | ✅ |
| C4 | Subtitle probe `--list-subs` recommended | ✅ | ❌ |
| C5 | `--embed-subs` for embedded subtitles | ✅ | ✅ |
| C6 | Chinese subtitle language code coverage | ✅ | ✅ |
| C7 | Nested playlist output template with truncation + zero-padding | ✅ | ❌ |
| C8 | `--download-archive` present | ✅ | ❌ |
| C9 | 7-field Output Contract complete | ✅ | ❌ |
| C10 | Probe section has format/subtitle probe commands | ✅ | ❌ |
| C11 | `--merge-output-format mp4` | ✅ | ❌ |
| C12 | Output directory `~/Videos/course/` | ✅ | ✅ |
| C13 | Mentions ffmpeg dependency | ✅ | ✅ |
| C14 | `--write-subs` paired with `--embed-subs` | ✅ | ❌ |
| C15 | Title truncation `%(title).200s` | ✅ | ❌ |

### 3.3 Classification of 22 Failed Assertions (Without-Skill)

| Failure type | Count | Evals | Notes |
|--------------|-------|-------|-------|
| **Missing 7-field Output Contract** | 3 | 1/2/3 | No structured Scenario/Inputs/Probe/Command/Status/Location/Next report |
| **Missing `--download-archive`** | 3 | 1/2/3 | Re-run would re-download all content |
| **Missing title truncation `%(title).200s`** | 3 | 1/2/3 | Long titles may cause filesystem path overflow |
| **Missing `--no-playlist` safety guard** | 2 | 1/2 | Single-video URL with list param may trigger full playlist download |
| **Missing Probe decision/subtitle probe** | 3 | 1/2/3 | Assumes subtitles exist without checking; no skip rationale |
| **Missing `--retries`/`--fragment-retries`** | 1 | 1 | Unstable network may cause download failure |
| **Missing Degraded mode declaration** | 1 | 1 | Does not state command was not executed |
| **Missing `--audio-quality 0`** | 1 | 2 | MP3 not using best VBR quality |
| **Missing `--yes-playlist` explicit declaration** | 1 | 3 | Playlist URL default behavior may be unstable |
| **Playlist template missing truncation + zero-padding** | 1 | 3 | `%(playlist_index)s` without zero-padding leads to wrong sort order |
| **Missing `--merge-output-format mp4`** | 1 | 3 | Output format uncertain (may be mkv/webm) |
| **Missing `--write-subs` with `--embed-subs`** | 1 | 3 | `--embed-subs` requires subtitles to be downloaded first |

### 3.4 Trend: Skill Advantage Increases with Scenario Complexity

| Scenario complexity | With-Skill advantage |
|---------------------|----------------------|
| Eval 1 (simple single video) | +58.3% (7 failures) |
| Eval 2 (medium dual-scenario) | +46.2% (6 failures) |
| Eval 3 (complex four-scenario overlay) | +60.0% (9 failures) |

Unlike the go-makefile-writer evaluation where "Skill advantage decreases with complexity", this skill is strongest in the most complex scenario. Reason: **yt-dlp command combinations have many implicit rules** (`--write-subs` with `--embed-subs`, playlist template zero-padding, SponsorBlock ffmpeg dependency, etc.); the base model omits more details when stacking multiple scenarios.

---

## 4. Dimension-by-Dimension Comparison

### 4.1 Output Contract (Structured Report)

This is a **Skill-only** differentiator, contributing 3 assertion deltas.

| Field | With Skill output | Without Skill output |
|-------|-------------------|----------------------|
| 1. Scenario | "Single video / Audio extraction + Subtitles / Composite: Playlist + Fixed Resolution + SponsorBlock + Subtitles" | None |
| 2. Inputs | Structured table (URL/dir/format/subs/auth) | Prose description |
| 3. Probe | Explicit decision (skipped + reason / recommended command) | None |
| 4. Final command | Full copy-paste command + table of reasons per flag | Command + brief param notes |
| 5. Execution status | "Not run in this environment" | No explicit declaration |
| 6. Output location | Expected file path pattern | Brief save location |
| 7. Next step | Ordered follow-up action list | Brief hint |

**Practical value**: Output Contract enables:
- Auditable command recommendations (know why specific flags were chosen)
- Transparent Probe decisions (whether probe was skipped and why)
- Clear next steps for users (no guessing)

### 4.2 Probe Decision Framework

This is the skill’s **core design advantage**, contributing 3 assertion deltas.

| Scenario | With Skill Probe decision | Without Skill |
|----------|---------------------------|---------------|
| Eval 1 | **Skipped** — public video, default best quality, no probe needed | No framework |
| Eval 2 | **`--list-subs` recommended** — subtitle availability unknown; probe before deciding `--write-subs` or `--write-auto-subs` | Assumes subtitles exist |
| Eval 3 | **3 probe commands** — playlist content, format availability, subtitle availability | No probe |

Without-skill’s key issue: assumes subtitles exist and adds `--write-subs` or `--embed-subs`; if subtitles don’t exist, silent failure. The skill’s Probe Gate forces verify-before-download.

### 4.3 Safety Guard Flags

| Flag | Purpose | With Skill | Without Skill |
|------|---------|-----------|--------------|
| `--no-playlist` | Prevent watch URL from accidentally triggering full playlist download | Eval 1 ✅ / Eval 2 ✅ | ❌ / ❌ |
| `--yes-playlist` | Explicitly declare playlist intent | Eval 3 ✅ | ❌ |
| `--download-archive` | Prevent re-download | 3/3 ✅ | 0/3 ❌ |
| `--retries`/`--fragment-retries` | Network resilience | 3/3 ✅ | 1/3 |
| `%(title).200s` | Prevent long title path overflow | 3/3 ✅ | 0/3 ❌ |

`--no-playlist` is the **highest-risk safety gap**. When a YouTube watch URL includes `&list=`, omitting `--no-playlist` downloads the entire playlist instead of one video, potentially causing tens of GB of accidental downloads. This is explicitly addressed in Skill Anti-Example #3.

### 4.4 Command Technical Correctness

| Detail | With Skill | Without Skill |
|--------|-----------|--------------|
| Format selector | `bv*+ba/b` (includes pre-merged fallback) | `bestvideo+bestaudio/best` (equivalent but no `*`) |
| Playlist template | `%(playlist_title).120s/%(playlist_index)05d` | `%(playlist)s/%(playlist_index)s` |
| Subtitle embed chain | `--write-subs --write-auto-subs + --embed-subs` | `--embed-subs` (missing `--write-subs`) |
| SponsorBlock categories | `sponsor,selfpromo,interaction` | `all` (may over-delete) |
| Audio quality | `--audio-quality 0` (best VBR) | Not specified (default quality 5) |

With-skill’s `bv*` selector is better than `bestvideo` because `*` includes pre-merged video streams (some sites only offer pre-merged format). Without-skill’s `bestvideo` does not include pre-merged streams.

### 4.5 Ambiguity Resolution Quality

In Eval 3, "Chinese subtitles" is ambiguous:

| Dimension | With Skill | Without Skill |
|-----------|-----------|--------------|
| Ambiguity identification | Explicitly notes "assumption: zh-Hans" and explains YouTube language tag inconsistency | No ambiguity analysis |
| Language code coverage | `zh-Hans,zh-Hant,zh` (three-code fallback chain) | `zh,zh-Hans,zh-Hant` |
| Fallback strategy | Explicitly recommends probe first; adjust if language codes differ | Brief "skip if no Chinese subtitles" |

Both cover three language codes, but With-skill’s ambiguity resolution is more transparent — users know why these codes were chosen and how to adjust.

---

## 5. Token Cost-Effectiveness Analysis

### 5.1 Skill Size

| File | Lines | Words | Bytes | Est. tokens |
|------|-------|-------|-------|-------------|
| **SKILL.md** | 214 | 1,298 | 9,742 | ~2,370 |
| references/scenario-templates.md | 168 | 548 | 5,053 | ~980 |
| references/decision-rules.md | 124 | 646 | 4,515 | ~870 |
| references/safety-and-recovery.md | 154 | 557 | 3,778 | ~730 |
| references/golden-examples.md | 110 | 497 | 4,290 | ~830 |
| references/format-selection-guide.md | 126 | 515 | 3,512 | ~680 |
| **Description (always in context)** | — | ~50 | — | ~70 |

### 5.2 Typical Load Scenarios

SKILL.md’s "Load References Selectively" section guides on-demand loading:

| Scenario | Files read | Total tokens |
|----------|------------|--------------|
| Simple download (Eval 1) | SKILL.md + scenario-templates + golden-examples | ~4,180 |
| Medium combination (Eval 2) | SKILL.md + scenario-templates + decision-rules + golden-examples | ~5,050 |
| Complex multi-scenario (Eval 3) | SKILL.md + scenario-templates + decision-rules + format-selection-guide + golden-examples | ~5,730 |
| Failure recovery | SKILL.md + safety-and-recovery | ~3,100 |
| Full load | All files | ~6,460 |

### 5.3 Token Cost for Quality Gain

| Metric | Value |
|--------|-------|
| With-skill pass rate | 100% (40/40) |
| Without-skill pass rate | 45.0% (18/40) |
| Pass-rate gain | +55.0 pp |
| Token cost per assertion fixed | ~108 tokens (SKILL.md only) / ~240 tokens (average full) |
| Token cost per 1% pass-rate gain | ~43 tokens (SKILL.md only) / ~95 tokens (average full) |

### 5.4 Token Segment Cost-Effectiveness

| Module | Est. tokens | Related assertion delta | Cost-effectiveness |
|--------|-------------|-------------------------|--------------------|
| **Output Contract definition** | ~200 | 3 assertions (3 evals 7-field report) | **Very high** — 67 tok/assertion |
| **Probe Gate decision framework** | ~250 | 3 assertions (probe skip/recommend) | **Very high** — 83 tok/assertion |
| **`--no-playlist` safety rule + Anti-Example #3** | ~80 | 2 assertions (Eval 1/2 missing guard) | **Very high** — 40 tok/assertion |
| **Safe defaults (archive/retries/truncation)** | ~150 | 7 assertions (3×archive + 1×retries + 3×truncation) | **Very high** — 21 tok/assertion |
| **`--yes-playlist` explicit declaration rule** | ~30 | 1 assertion | **Very high** — 30 tok/assertion |
| **Audio quality 0 rule** | ~20 | 1 assertion | **Very high** — 20 tok/assertion |
| **`--write-subs` + `--embed-subs` chain** | ~40 | 1 assertion | **Very high** — 40 tok/assertion |
| **Playlist template truncation + zero-padding** | ~30 | 1 assertion | **Very high** — 30 tok/assertion |
| **`--merge-output-format mp4` rule** | ~20 | 1 assertion | **Very high** — 20 tok/assertion |
| **Degraded mode framework** | ~100 | 1 assertion | **High** — 100 tok/assertion |
| **Gate pipeline architecture (7 gates diagram)** | ~300 | Indirect (structured thinking) | **Medium** — no direct assertion |
| **Anti-Examples (8)** | ~350 | Indirect (avoid hardcoded format ID, etc.) | **Medium** — indirect |
| **Scope Classification table** | ~120 | Indirect (correct scenario classification) | **Medium** — indirect |
| **Auth Safety Gate** | ~100 | 0 (no auth scenario in this eval) | **Low** — not tested |
| **Live Stream rules** | ~50 | 0 (no live stream in this eval) | **Low** — not tested |

### 5.5 High-Leverage vs Low-Leverage Instructions

**High leverage (~820 tokens SKILL.md → 20 assertion deltas):**
- Safe defaults (150 tok → 7 assertions)
- Probe Gate (250 tok → 3 assertions)
- Output Contract (200 tok → 3 assertions)
- `--no-playlist` rule (80 tok → 2 assertions)
- Other single-rule items (140 tok → 5 assertions)

**Medium leverage (~770 tokens → indirect):**
- Anti-Examples (350 tok) — avoid hardcoded format ID
- Gate pipeline (300 tok) — drive structured thinking flow
- Scope classification (120 tok) — correct multi-scenario overlay identification

**Low leverage (~150 tokens → 0 deltas):**
- Auth Safety (100 tok) — no auth scenario in this eval
- Live Stream (50 tok) — no live stream in this eval

**References (~3,090–4,090 tokens → indirect):**
- scenario-templates.md drives command completeness and flag selection
- golden-examples.md drives answer format consistency
- decision-rules.md drives format selection technical correctness

### 5.6 Token Efficiency Rating

| Rating | Conclusion |
|--------|------------|
| **Overall ROI** | **Excellent** — ~5,000 tokens for +55% pass rate |
| **SKILL.md ROI** | **Outstanding** — ~2,370 tokens contains all high-leverage rules |
| **High-leverage token share** | ~35% (820/2,370) directly contributes to 20/22 assertion deltas |
| **Low-leverage token share** | ~6% (150/2,370) no incremental contribution in this eval |
| **Reference cost-effectiveness** | **Good** — indirectly improves command completeness and technical correctness |

### 5.7 Comparison with Other Skills’ Cost-Effectiveness

| Metric | yt-dlp-downloader | go-makefile-writer | tdd-workflow |
|--------|-------------------|-------------------|--------------|
| SKILL.md tokens | ~2,370 | ~1,960 | ~2,100 |
| Total load tokens | ~5,100–5,730 | ~4,100–4,600 | ~3,600–4,800 |
| Pass-rate gain | **+55.0%** | +31.0% | +46.2% |
| Tokens per 1% (SKILL.md) | **~43 tok** | ~63 tok | ~45 tok |
| Tokens per 1% (full) | **~95 tok** | ~149 tok | ~92 tok |

yt-dlp-downloader has **best token cost-effectiveness** among the three skills because:
1. Base model has weaker grasp of yt-dlp’s implicit rules (45% baseline vs go-makefile 69%), more room for improvement
2. Skill’s high-leverage rules are compact (safe defaults, probe gate, output contract only ~820 tokens)
3. Reference conditional loading is well designed; simple scenarios don’t load everything

---

## 6. Boundary Analysis vs Base Model Capabilities

### 6.1 Capabilities Base Model Already Has (No Skill Increment)

| Capability | Evidence |
|------------|----------|
| `-f "bestvideo+bestaudio/best"` format selection | 3/3 scenarios correct |
| `--merge-output-format mp4` | 2/3 scenarios correct (Eval 3 omitted) |
| `-x --audio-format mp3` audio extraction | 1/1 scenario correct |
| `--convert-subs srt` format conversion | 1/1 scenario correct |
| `[height<=720]` resolution cap | 1/1 scenario correct |
| `--sponsorblock-remove` basic usage | 1/1 scenario correct |
| `--embed-subs` subtitle embedding | 1/1 scenario correct |
| Chinese subtitle multi-language code coverage | 1/1 scenario correct |
| ffmpeg dependency prompt | 3/3 scenarios correct |
| Output path basically correct | 3/3 scenarios correct |

### 6.2 Base Model Gaps (Skill Fills)

| Gap | Evidence | Risk level |
|-----|----------|------------|
| **Missing `--no-playlist` safety guard** | 2/2 single-video scenarios missing | **High** — may accidentally download entire playlist |
| **Missing `--download-archive`** | 3/3 scenarios missing | **Medium** — re-run re-downloads |
| **Missing title truncation** | 3/3 scenarios use `%(title)s` | **Medium** — long title path overflow |
| **No Probe decision framework** | 3/3 scenarios no probe awareness | **Medium** — assumes subtitles exist, silent failure |
| **No structured Output Contract** | 3/3 scenarios no report | **Medium** — command recommendations lack auditability |
| **`--write-subs` + `--embed-subs` chain** | 1/1 scenario omitted | **High** — subtitle embed silent failure |
| **Playlist template zero-padding** | 1/1 scenario missing | **Low** — sort order wrong but usable |
| **`--audio-quality 0`** | 1/1 scenario missing | **Low** — default quality slightly lower but acceptable |
| **Degraded mode declaration** | 1/3 scenarios missing | **Low** — user may think command was executed |

---

## 7. Overall Score

### 7.1 Dimension Scores

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| Command technical correctness | 5.0/5 | 3.5/5 | +1.5 |
| Safety guards (no-playlist/archive/truncation) | 5.0/5 | 1.5/5 | +3.5 |
| Probe decision framework | 5.0/5 | 1.0/5 | +4.0 |
| Structured report (Output Contract) | 5.0/5 | 1.0/5 | +4.0 |
| Multi-scenario overlay handling | 5.0/5 | 3.0/5 | +2.0 |
| Ambiguity resolution | 5.0/5 | 2.5/5 | +2.5 |
| **Overall mean** | **5.0/5** | **2.08/5** | **+2.92** |

### 7.2 Weighted Total Score

| Dimension | Weight | Score | Weighted |
|-----------|-------|------|----------|
| Assertion pass rate (delta) | 25% | 10/10 | 2.50 |
| Safety guards | 20% | 10/10 | 2.00 |
| Probe decision + ambiguity resolution | 15% | 10/10 | 1.50 |
| Output Contract | 10% | 10/10 | 1.00 |
| Multi-scenario overlay handling | 10% | 10/10 | 1.00 |
| Token cost-effectiveness | 15% | 9.0/10 | 1.35 |
| Command technical correctness increment | 5% | 7.0/10 | 0.35 |
| **Weighted total** | | | **9.70/10** |

Command technical correctness increment is scored lower because Without-skill’s core commands are technically sound — the base model has good grasp of basic yt-dlp usage; the skill’s core value is **safety guards**, **Probe discipline**, and **structured reports**.

---

## 8. Evaluation Materials

| Material | Path |
|----------|------|
| Eval 1 with-skill output | `/tmp/ytdlp-eval/eval-1/with_skill/response.md` |
| Eval 1 without-skill output | `/tmp/ytdlp-eval/eval-1/without_skill/response.md` |
| Eval 2 with-skill output | `/tmp/ytdlp-eval/eval-2/with_skill/response.md` |
| Eval 2 without-skill output | `/tmp/ytdlp-eval/eval-2/without_skill/response.md` |
| Eval 3 with-skill output | `/tmp/ytdlp-eval/eval-3/with_skill/response.md` |
| Eval 3 without-skill output | `/tmp/ytdlp-eval/eval-3/without_skill/response.md` |
