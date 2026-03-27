---
title: yt-dlp-downloader skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# yt-dlp-downloader Skill Design Rationale

`yt-dlp-downloader` is a probe-first framework for generating and, when possible, executing yt-dlp download commands. Its core idea is: **the hard part of high-quality yt-dlp assistance is determining what the user is actually trying to download, what formats and subtitles are really available, whether a watch URL might accidentally trigger a full playlist, whether the current environment can safely execute the command, and ensuring that a recommended command is never presented as a successful download unless it actually ran.** That is why the skill turns Scope Classification, Dependency, Ambiguity Resolution, Probe, Auth Safety, Execution Mode, and Execution Integrity into one fixed seven-gate workflow.

## 1. Definition

`yt-dlp-downloader` is used for:

- generating and, when conditions permit, executing yt-dlp download commands,
- handling single videos, fixed resolution downloads, playlists, audio extraction, subtitles, authenticated content, live streams, and SponsorBlock use cases,
- making format and subtitle decisions from probes rather than guessed format IDs or language codes,
- applying safe defaults such as archive, resume, no-overwrite, retries, and truncated output paths,
- and reporting execution status in a structured way so users know whether the command actually ran and what to do next.

Its output is not just the final command. It also includes:

- scenario,
- inputs,
- probe decision or probe-result summary,
- final command,
- execution status,
- output location,
- next step.

From a design perspective, it is closer to a download-command governance framework than to a quick yt-dlp parameter prompt.

## 2. Background and Problems

The skill is not solving "models do not know yt-dlp." It is solving the fact that default download advice tends to drift into several high-risk distortions:

- guessing format IDs, subtitle languages, or resolution selectors without probing,
- accidentally downloading a full playlist when the user only wanted one video,
- reporting or implying success even though no command was actually executed.

Without an explicit process, the most common failures cluster into eight categories:

| Problem | Typical consequence |
|---------|---------------------|
| No scenario classification first | playlist, subtitle, audio-extraction, and SponsorBlock rules get mixed together |
| No dependency check first | merge / extract / embed commands are recommended even when `ffmpeg` is unavailable |
| No ambiguity resolution | the assistant does not know whether the user wants the full playlist, one video, or which subtitle language |
| No probe step | format IDs, subtitle availability, and playlist scale are guessed |
| No auth-safety boundary | cookies drift into paywall / DRM / circumvention advice |
| No safe defaults | re-downloads, title-path overflow, and poor recovery under unstable networks |
| Execution status is not stated honestly | users think the file was downloaded when only a command was recommended |
| No structured report for complex requests | commands can be reused less safely because users cannot tell why the flags were chosen |

The design logic of `yt-dlp-downloader` is to answer "what scenario is this, what is still ambiguous, which formats and subtitles really exist, whether auth is required, whether the environment can execute, and how to degrade honestly if it cannot" before assembling the final command.

## 3. Comparison with Common Alternatives

It helps to compare it with a few common alternatives:

| Dimension | `yt-dlp-downloader` skill | Asking a model to "give me a yt-dlp command" | Writing a familiar command from memory |
|-----------|---------------------------|----------------------------------------------|---------------------------------------|
| Scenario classification | Strong | Weak | Weak |
| Probe discipline | Strong | Weak | Weak |
| Playlist safety guard | Strong | Weak | Weak |
| Safe defaults | Strong | Weak | Weak |
| Auth-safety boundary | Strong | Medium | Weak |
| Honest degradation | Strong | Weak | Weak |
| Structured execution report | Strong | Weak | Weak |
| Multi-scenario overlay handling | Strong | Medium | Weak |

Its value is not only that the command looks more complete. Its value is that download advice becomes safer, more auditable, and more reusable under real-world conditions.

## 4. Core Design Rationale

### 4.1 Scope Classification Comes First

The first step in `yt-dlp-downloader` is not command generation. It is mapping the request into one primary scenario:

- Single video,
- Fixed resolution,
- Playlist,
- Audio extraction,
- Subtitles,
- Authenticated,
- Live stream,
- SponsorBlock.

If the request is composite, the skill requires selecting a primary scenario first, then overlaying secondary flags, and documenting the composition in the Output Contract's Scenario field.

This is critical because many yt-dlp mistakes are not caused by a single wrong flag. They come from mixing multiple scenarios without choosing a stable base template. A request like "playlist + 720p + SponsorBlock + Chinese subtitles" is not just four independent wishes. It needs a Playlist base template first, then resolution, SponsorBlock, and subtitle logic layered on top. The evaluation's most complex case showed exactly this: the skill's advantage was not basic syntax, but combination discipline.

### 4.2 The Dependency Gate Must Be Up Front

Before execution, the skill requires checking:

- `yt-dlp --version`,
- `ffmpeg -version`.

It also explicitly states that `ffmpeg` is required for:

- merging video + audio,
- embedding subtitles,
- extracting audio,
- embedding thumbnails,
- and `--merge-output-format`.

It further adds the `yt-dlp-ejs + JS runtime` requirement for full YouTube support, which explains a major class of extraction failures.

This is mature design because many failures that look like "command problems" are really environment problems. Without this gate, it is easy for an assistant to misdiagnose the issue as a bad URL or bad format choice instead of first checking the dependency chain.

### 4.3 The Ambiguity Resolution Gate Is So Strict

`yt-dlp-downloader` explicitly stops to ask when:

- no URL is provided,
- the output directory is missing and matters for batch/playlist downloads,
- "good quality" is too vague,
- a playlist URL is given but full-playlist vs single-video intent is unclear,
- subtitles are requested without a language,
- multiple URLs are given without clear batching intent.

This matters because download tasks often look simpler than they are. One missing clarification can completely change the correct command. The canonical example is the YouTube watch URL with `list=`: if intent is not clarified, a single-video request can silently turn into full-playlist behavior.

### 4.4 The Probe Gate Is the Core of the Skill

The Probe Gate is the skill's most distinctive design choice. It explicitly requires:

- `yt-dlp -F` for specific resolution / codec / format requests,
- `yt-dlp --list-subs` when subtitle availability matters,
- `--flat-playlist` when playlist scale is unclear or large,
- `--simulate --skip-download` when auth or redirects may matter.

And it only permits probe skipping in the simple case of a public single video where the user already accepts default best quality.

This is the methodological core of the skill. In the evaluation, Probe decision compliance was one of the clearest skill-only deltas: with-skill was `3/3`, without-skill was `0/3`. That shows the real increment is not "knowing more yt-dlp flags." It is knowing when experience-based guessing is not acceptable.

### 4.5 `--no-playlist` Is a Safety Rule While `--yes-playlist` Is an Explicit-Intent Rule

The skill constrains playlist behavior at two different levels:

- single-video watch URLs default to `--no-playlist`, which is explicitly written into the skill's Safety Rules,
- full playlist intent should be made explicit with `--yes-playlist`, which serves as the corresponding explicit-intent decision rule.

This matters because it addresses one of the highest-risk baseline gaps found in the evaluation. YouTube watch URLs frequently carry `&list=` parameters, and omitting `--no-playlist` can trigger large accidental downloads with major time, bandwidth, and storage costs.

That is why `--no-playlist` is not treated as a cosmetic recommendation. It is a safety rule. `--yes-playlist` matters for the opposite reason: when the user truly wants the full playlist, the command should say so explicitly instead of relying on ambiguous default behavior.

### 4.6 Safe Defaults Are Fixed as a Default Contract

The skill's defaults are not a loose grab bag. They are a stable set:

- `--download-archive`,
- `--continue`,
- `--no-overwrites`,
- `--retries 10 --fragment-retries 10`,
- `-o "<dir>/%(title).200s [%(id)s].%(ext)s"`.

For batches, troubleshooting, or unstable networks, it also recommends `tee`-based logging.

This is mature design because many yt-dlp problems are not failures to run the command at all. They are failures of repeatability and resilience:

- a rerun downloads everything again,
- interrupted downloads do not resume,
- long titles overflow the path,
- large runs fail without useful logs.

In the evaluation, archive / retries / truncation were among the most stable skill-only advantages. That shows these defaults improve execution reliability rather than just command syntax.

### 4.7 The Auth Safety Gate Separates "Can" from "Should"

The skill supports cookies and browser-session extraction, but it also sets very clear boundaries:

- cookies are only for content the user is authorized to access,
- `--cookies-from-browser` is preferred,
- users must never paste raw cookies into chat,
- cookies must never be described as a way to bypass paywalls, DRM, or geographic restrictions.

This is important because yt-dlp guidance naturally risks drifting into technically possible but inappropriate assistance. `yt-dlp-downloader` preserves legitimate authenticated-access workflows while blocking abusive framing at the rule level.

### 4.8 Execution Mode and Honest Degradation Are Separate Layers

`yt-dlp-downloader` auto-selects among:

- Full,
- Degraded,
- Blocked.

And it explicitly defines them as:

- Full: dependencies are present and the command actually ran, so success / failure details can be reported,
- Degraded: only a recommended command and assumptions may be given; no success, file size, or format availability claims,
- Blocked: `yt-dlp` is missing, or the request involves DRM / unauthorized access, so the blocker must be stated directly. Other missing prerequisites, such as `ffmpeg` for a merge/extract/embed request, should be reported as request-specific blockers with install guidance rather than widening the mode definition itself.

This is especially important because download assistance easily creates a false sense of execution: the command looks complete, so the user assumes the job is done. The skill forces a clean boundary between "command recommendation" and "command execution."

### 4.9 The Execution Integrity Gate Is the Final Honesty Constraint

The skill explicitly requires:

- if the command ran, report destination, success/failure, and relevant stderr/stdout summary,
- if it did not run, say `Not run in this environment`.

This is critical because assistants often produce language that sounds like successful execution even when no shell execution happened. In the evaluation, without-skill missed degraded-mode declaration, while with-skill made "not run" part of the contract itself. This lets users distinguish between:

- whether the command looks reasonable,
- whether the command actually executed.

### 4.10 Output Contract as a Second Major Design Axis

`yt-dlp-downloader` requires every response to include seven fields:

1. Scenario
2. Inputs
3. Probe
4. Final command
5. Execution status
6. Output location
7. Next step

The value of this is not just tidiness. It makes a complex download command auditable:

- which scenario template was chosen,
- which inputs were user-provided versus assumed,
- whether probing was skipped or performed and why,
- what to change next if the command fails.

In the evaluation, Output Contract compliance was a clear skill-only difference: with-skill `3/3`, without-skill `0/3`.

### 4.11 Multi-Scenario Overlay Handling Is So Valuable

Real yt-dlp requests are often combinations such as:

- playlist + resolution cap,
- subtitles + embedding,
- audio extraction + subtitle saving,
- SponsorBlock + MP4 output.

`yt-dlp-downloader` does not flatten these into an arbitrary pile of flags. It insists on:

- choosing a base scenario template first,
- overlaying secondary scenario rules second,
- documenting the composite relationship in the report.

That gives complex requests a stable structure instead of relying on last-step flag improvisation.

### 4.12 The Real Increment Is Workflow Governance vs. Basic Syntax

The evaluation already shows that the baseline model knew a fair amount of basic yt-dlp syntax, including:

- `bestvideo+bestaudio/best`,
- `--audio-format mp3`,
- `[height<=720]`,
- `--sponsorblock-remove`,
- `--embed-subs`.

The real gaps were elsewhere:

- missing `--no-playlist`,
- missing `--download-archive`,
- missing title truncation,
- no Probe framework,
- no Output Contract,
- no awareness that `--write-subs` must pair with `--embed-subs`,
- no honest degraded-mode declaration.

That means the core value of `yt-dlp-downloader` is not teaching yt-dlp from zero. It is making real download assistance safer, more explicit, and more reproducible.

## 5. Problems This Design Solves

Combining the current `SKILL.md`, key references, and the evaluation report, the skill solves the following problems:

| Problem type | Corresponding design | Practical effect |
|--------------|----------------------|------------------|
| Wrong base template for mixed requests | Scope Classification | Command structure becomes more stable |
| Commands fail because dependencies are missing | Dependency Gate | Failure diagnosis improves |
| User intent is under-specified | Ambiguity Resolution Gate | Fewer misdownloads |
| Formats or subtitles are guessed | Probe Gate | Parameter choice becomes more reliable |
| Single-video intent triggers full-playlist download | `--no-playlist` / `--yes-playlist` rules | Safety improves sharply |
| Repeat runs, interrupted transfers, or path issues | Safe defaults | Execution resilience improves |
| Cookie advice drifts out of bounds | Auth Safety Gate | Safety boundaries stay clear |
| Recommended commands look like completed downloads | Execution Integrity + Honest Degradation | Reporting stays honest |

## 6. Key Highlights

### 6.1 Probe-First Is the Skill's Most Distinctive Design Choice

It turns "inspect available formats and subtitles first" into a hard workflow rather than an optional best practice.

### 6.2 The Playlist Safety Guard Is Exceptionally Practical

`--no-playlist` / `--yes-playlist` blocks one of the most common and expensive yt-dlp mistakes before execution.

### 6.3 Safe Defaults Are Core Reliability Infrastructure, Not Decoration

Archive, resume, retries, and title truncation directly address repeatability, resilience, and filesystem safety.

### 6.4 Honest Degradation Rigidly Separates Recommendation from Execution

That prevents users from mistaking a suggested command for a completed download.

### 6.5 The Output Contract Makes Complex Commands Reviewable

In multi-scenario requests especially, the Scenario / Probe / Next step fields greatly improve explainability.

### 6.6 Its Real Increment Is Safety and Process, Not Basic Syntax Knowledge

The evaluation already shows that the baseline's basic yt-dlp syntax was often reasonable. The real improvement came from probe discipline, safety defaults, playlist guards, structured reporting, and execution honesty. That means the core value of `yt-dlp-downloader` is command governance rather than parameter encyclopedism.

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Single videos, playlists, audio extraction, subtitle downloads | Very suitable | These are core use cases |
| Composite requests such as playlist + 720p + subtitles + SponsorBlock | Very suitable | The overlay model is strong here |
| Auth-required content the user is legitimately allowed to access | Suitable | Auth safety rules are explicit |
| Environments without shell access or without yt-dlp installed | Suitable | Degraded / Blocked modes exist |
| Requests to bypass DRM, paywalls, or unauthorized access restrictions | Not suitable | Explicitly blocked by safety rules |

## 8. Conclusion

The real strength of `yt-dlp-downloader` is not that it writes longer yt-dlp commands. It is that it systematizes the parts of download assistance that are most likely to go wrong: classify the scenario first, check dependencies, resolve ambiguities, probe actual format and subtitle availability, and then constrain the final command and report with safe defaults, playlist guards, auth safety, and honest degradation.

From a design perspective, the skill expresses a clear principle: **the key to high-quality yt-dlp assistance is not knowing more flags, but knowing when probing is mandatory, when the assistant must stop and ask, when the request crosses a safety boundary, and when an unexecuted command must never be presented as a completed result.** That is why it is especially well suited to real downloads, batch downloads, and complex composite download requests.

## 9. Document Maintenance

This document should be updated when:

- the seven gates, Defaults, Safety Rules, Honest Degradation, Output Contract, or selective-loading rules in `skills/yt-dlp-downloader/SKILL.md` change,
- key rules in `skills/yt-dlp-downloader/references/scenario-templates.md`, `decision-rules.md`, `format-selection-guide.md`, `safety-and-recovery.md`, `anti-examples.md`, or `golden-examples.md` change,
- the core supporting results in `evaluate/yt-dlp-downloader-skill-eval-report.md` or `evaluate/yt-dlp-downloader-skill-eval-report.zh-CN.md` change.

Review quarterly; review immediately if the probe rules, safe defaults, playlist guards, or execution contract of `yt-dlp-downloader` change substantially.

## 10. Further Reading

- `skills/yt-dlp-downloader/SKILL.md`
- `skills/yt-dlp-downloader/references/scenario-templates.md`
- `skills/yt-dlp-downloader/references/decision-rules.md`
- `skills/yt-dlp-downloader/references/format-selection-guide.md`
- `skills/yt-dlp-downloader/references/safety-and-recovery.md`
- `skills/yt-dlp-downloader/references/anti-examples.md`
- `skills/yt-dlp-downloader/references/golden-examples.md`
- `evaluate/yt-dlp-downloader-skill-eval-report.md`
- `evaluate/yt-dlp-downloader-skill-eval-report.zh-CN.md`
