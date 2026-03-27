---
title: local-transcript skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# local-transcript Skill Design Rationale

`local-transcript` is an end-to-end transcription delivery framework for local audio and video files. Its core idea is: **the goal of transcription is to turn a local media file into a finished deliverable by explicitly handling format resolution, dependency checks, audio extraction, ASR selection, Chinese cleanup, LLM proofreading, paragraphing, cache reuse, and final-file export.** That is why the skill links Format Resolution, Dependency, ASR mode selection, three-layer caching, the Chinese cleanup pipeline, and structured reporting into one explicit workflow.

## 1. Definition

`local-transcript` is used for:

- turning a local audio or video file into `txt`, `pdf`, or `docx`,
- converting Chinese transcripts into simplified Chinese with normalized punctuation and natural paragraphs,
- correcting common Whisper mistakes through deterministic replacements plus LLM proofreading,
- preferring GPU-accelerated `mlx-whisper` on Apple Silicon,
- falling back to `faster-whisper` when needed,
- reducing repeat-run cost through layered cache reuse.

Its output is not only the transcript text. It also includes:

- the input file,
- the detected or inferred language,
- the ASR backend, mode, and model,
- LLM proofreading status,
- requested output formats,
- cache status for audio / raw transcript / clean transcript,
- final output paths,
- total processing time,
- and whether cleaning completed successfully.

From a design perspective, it is closer to a local transcription delivery pipeline than to a prompt that merely knows how to invoke Whisper.

## 2. Background and Problems

The main problem this skill addresses is not that agents cannot invoke transcription tools. It is that local transcription tasks often stop at an awkward intermediate state:

- recognition runs, but too slowly,
- text appears, but quality is poor,
- output exists, but still falls far short of a reusable deliverable.

Without a clear framework, the most common failures cluster into eight categories:

| Problem | Typical consequence |
|---------|---------------------|
| Only bare ASR is run | The output remains full of homophone errors, semantic mistakes, and broken paragraph structure |
| Backend selection is poor | Apple Silicon still runs a CPU path and wastes the machine's main advantage |
| Simplified/traditional conversion and punctuation are ignored | Chinese output is inconsistent and not ready for delivery |
| Systematic ASR errors and contextual errors are treated the same way | Cleanup remains highly manual and hard to reuse |
| Proper nouns are not unified | The same person, place, or term appears under multiple spellings |
| No cache exists | Every rerun repeats the full pipeline from scratch |
| Output format is not treated as an explicit requirement | The user still has to manually convert into `pdf` or `docx` |
| Backend / model / cache / timing are not reported honestly | The user gets a file but cannot tell how it was produced |

The design logic of `local-transcript` is to decompose "how do we reliably produce a finished transcript artifact?" into explicit stages, then assign stable defaults and fallback paths to each stage.

## 3. Comparison with Common Alternatives

It helps to compare the skill with a few common alternatives:

| Dimension | `local-transcript` skill | Running Whisper once directly | Manual cleanup after a raw transcript |
|-----------|--------------------------|-------------------------------|---------------------------------------|
| End-to-end workflow completeness | Strong | Weak | Medium |
| Apple Silicon performance use | Strong | Weak | Weak |
| Chinese cleanup and simplified normalization | Strong | Weak | Medium |
| Homophone and semantic correction | Strong | Weak | Medium |
| Proper-noun consistency | Strong | Weak | Weak |
| Cache reuse | Strong | Weak | Weak |
| Multi-format final export | Strong | Weak | Weak |
| Auditability | Strong | Weak | Weak |

Its value is not only that it turns audio into text. Its value is that it upgrades transcription from one-shot recognition into a repeatable, deliverable, reusable local document-production workflow.

## 4. Core Design Rationale

### 4.1 It Treats "Finished Deliverable" as the Goal vs. "Raw Transcript"

From the beginning, `local-transcript` defines the output as:

- a cleaned final transcript,
- in `txt`, `pdf`, or `docx`,
- with natural paragraphing,
- and language / punctuation normalization where needed.

This is critical because most transcription workflows stop after ASR. The evaluation makes the gap very clear: without-skill can already produce 5000+ characters, but the result is still 917 short lines, traditional Chinese, mixed punctuation, and uncorrected errors. With-skill is the one that actually reaches a reusable document.

### 4.2 The Format Resolution Gate Must Be Explicit

At the skill layer, output format is not allowed to be guessed when the user has not specified it. It instead requires:

- direct use of `txt`, `pdf`, or `docx` when explicitly requested,
- generating all requested outputs when multiple formats are named,
- asking a short follow-up if the user asked for transcription but not the output format.

The underlying script still keeps a direct-CLI default of `txt`, but the skill intentionally treats explicit format confirmation as part of the execution discipline.

This is a direct design choice because "transcribe this" is not only a processing request; it is also a delivery request. Whether the user wants `txt`, `pdf`, or `docx` changes the later export path, font handling, and final usability. So the skill treats format as a required execution input, not as a contextual guess.

### 4.3 The Dependency Gate Comes Before Real Execution

`local-transcript` makes its dependency surface explicit and validates different dependency classes at different points:

- `ffmpeg`,
- local Python execution,
- `mlx-whisper`,
- `mlx-lm`,
- `faster-whisper`,
- `opencc`,
- `reportlab`,
- `python-docx`,
- optionally the `claude` CLI,
- and CJK font availability for Chinese PDF output.

The value of this design is that it makes dependency requirements explicit and moves as much failure as possible earlier. Transcription tasks tend to be expensive in runtime, so discovering that `ffmpeg` is missing halfway through is costly. The implementation is layered, though: system-level prerequisites surface early, Python dependencies such as `mlx-whisper`, `mlx-lm`, and `faster-whisper` are loaded and validated only when their execution paths are entered, the `claude` CLI is an optional backend that currently degrades at runtime, and Chinese PDF font availability is checked when PDF writing happens. So the most accurate description is "dependency requirements are explicit; early checks happen where possible; branch-specific dependencies are validated on the path that needs them."

### 4.4 The Default Backend Is `mlx` vs. a More General CPU Path

The default backend in `local-transcript` is `mlx`, favoring Apple Silicon GPU execution.

The value of this choice is clear because one of the real engineering gains in this kind of local workflow is not merely "knowing about Whisper," but knowing that:

- Apple Silicon should default to `mlx-whisper`,
- larger and better models can still run much faster on the right hardware,
- CPU transcription is a fallback path, not the main path.

The evaluation makes this very visible: the with-skill ASR stage took 116.4s, while the without-skill CPU path took about 670s, a 5.8x slowdown. More importantly, the with-skill run used the larger model and still finished faster. That means the skill is not making a speed-vs-quality trade-off; it is making correct use of platform-specific capability.

### 4.5 `fast`, `balanced`, and `accurate` Are Fixed Presets

The skill does not expose users directly to a pile of low-level ASR parameters. Instead it collapses them into three presets:

- `fast`,
- `balanced`,
- `accurate`.

The key point here is that the main user decision in transcription is usually not "what beam size should I use?" but:

- do I care more about speed or quality right now,
- can this machine afford a more expensive path,
- will LLM proofreading also be used as a second-stage correction layer.

Fixed presets hide unnecessary tuning complexity while still preserving understandable behavior differences. That makes delivery more stable and reduces trial-and-error.

### 4.6 Three-Layer Caching Is a Core Engineering Choice

`local-transcript` caches three layers:

- extracted WAV audio,
- raw ASR transcript,
- cleaned final transcript.

This is especially important because transcription workflows naturally have high rerun cost and frequent repeated exports. A user may:

- first want `txt`,
- then later ask for `pdf`,
- or rerun the same transcription request for the same input.

What the current script supports most clearly is reusing work for identical inputs and avoiding repeated audio extraction or ASR for format-only re-exports. It does not expose a standalone "refresh clean layer only" path, and the clean-cache key is not modeled around every cleanup option change. So the design should be understood as "reduce repeated work substantially" rather than "any stage can be rerun independently at will."

### 4.7 Chinese Cleanup Is Designed as a Multi-Layer Pipeline

The Chinese cleanup path in `local-transcript` is deliberately layered:

1. simplified-Chinese conversion,
2. deterministic replacements,
3. contextual LLM proofreading,
4. post-LLM safety replacements,
5. proper-noun unification.

This works well because Chinese transcription errors are not all the same kind of error:

- some are systematic high-frequency ASR mistakes,
- some require sentence-level context to fix,
- some only become visible as document-wide inconsistency.

Rules alone cannot solve the contextual cases. LLM alone is slower and needlessly expensive for already-known Whisper failure modes. The layered design lets each mechanism solve the type of error it handles best.

### 4.8 Deterministic Replacements and LLM Proofreading Coexist

By default, the script uses a built-in Chinese replacement table, while also allowing an optional external JSON replacement file and an LLM proofreading layer.

The design value is that it separates two error families:

- universal, cross-video Whisper bugs,
- video-specific, domain-specific, or contextual mistakes.

The first family is best handled by deterministic replacement because it is almost free and highly reliable. The second family needs LLM context. In the evaluation, examples such as `大便车` → `搭便车` and `配剂制` → `配给制` show the value of the rule-based layer, while the document-wide consistency around "哈萨尼" shows why contextual correction and post-processing still matter.

### 4.9 LLM Proofreading Is On by Default for Chinese but Off by Default for English

The skill explicitly defines:

- LLM proofreading on by default for Chinese,
- off by default for English,
- but available for English through `--llm-proofread-en` when needed.

This is a sensible default strategy because:

- Chinese ASR output is much more likely to contain homophone, near-sound, simplified/traditional, and punctuation issues,
- many English cases are acceptable with raw ASR output,
- LLM proofreading is also the main runtime cost in the full pipeline.

In other words, the skill does not blindly add LLM to everything. It makes a language-sensitive default decision based on expected quality gain per unit of runtime.

### 4.10 Proper-Noun Unification Happens After the LLM Pass

`local-transcript` performs an additional limited CJK variant-consolidation pass after LLM proofreading, merging certain low-frequency near-duplicate forms into a dominant form when they match the script's heuristics.

This is useful because even when the LLM fixes many local mistakes, the same name can still appear in slightly different forms across chunks. This pass is not general entity resolution; it is a bounded document-level consistency safeguard for short CJK variants. The "哈萨尼" example from the evaluation shows this value directly.

### 4.11 Externalizing the Script Is Such an Important Skill Design Choice

The core capability of `local-transcript` is not only written in `SKILL.md`; a much larger share of the engineering logic lives in `scripts/local_transcript.py`.

This is highly efficient because:

- the complex execution logic does not need to be loaded into the model context every time,
- the skill can stay focused on orchestration and parameter strategy,
- the real engineering capability executes through the script at near-zero context cost.

This is also a major reason the token efficiency is so strong in the evaluation: more than a thousand lines of execution logic run through the script rather than consuming model context.

### 4.12 Output Contract with Backend, Cache, and Cleaning Status

The Output Contract requires:

- input,
- language,
- backend,
- mode,
- model,
- LLM proofreading status,
- requested formats,
- cache status,
- final paths,
- total time,
- cleaning success state.

The value here is that the result becomes more than "here is your file." It becomes "here is the execution path the run was intended to use." That matters for:

- reproducing problems,
- comparing different modes,
- checking whether cache reuse actually happened,
- tracking whether the result went through cleaning and LLM proofreading.

It makes local media processing far less of a black box. The current implementation still has edge cases, such as runtime fallback when the `claude` backend is unavailable, so this is closer to a high-visibility execution record than to a perfectly precise audit log.

## 5. Problems This Design Solves

Combining the current `SKILL.md`, script behavior, and the evaluation report, the skill solves the following problems:

| Problem type | Corresponding design | Practical effect |
|--------------|----------------------|------------------|
| Raw ASR output is not reusable | End-to-end workflow + final export | Produces directly usable document artifacts |
| Apple Silicon performance is wasted | Default `mlx` backend | Improves both speed and quality |
| Chinese homophone and semantic errors remain | Deterministic replacements + LLM proofreading | Raises Chinese transcript accuracy systematically |
| Simplified/traditional and punctuation are inconsistent | OpenCC + punctuation normalization | Makes output more natural for Chinese reading |
| The same proper noun appears under many spellings | Proper-noun unification | Improves document-wide consistency |
| Rerun cost is too high | Three-layer audio/raw/clean cache | Reduces rerun cost for repeated execution of the same input and for format re-exports |
| Output format needs are left implicit | Format Resolution Gate | Prevents wrong-format delivery |
| Execution is hard to audit | Output Contract | Makes backend, mode, cache, timing, and success state visible |

## 6. Key Highlights

### 6.1 It Treats Transcription as Document Delivery, Not Speech Recognition

This is the most important positioning difference in the skill. Its target is the finished transcript artifact, not the raw recognition output.

### 6.2 Its Apple Silicon Default Path Is a Major Engineering Strength

`mlx-whisper` plus local GPU execution is one of the skill's biggest engineering advantages, and the evaluation validated this directly.

### 6.3 Its Chinese Cleanup Pipeline Is Unusually Complete

Simplified conversion, deterministic replacements, LLM proofreading, post-LLM safety, and proper-noun unification form a very clear layered system.

### 6.4 Its Layered Cache Matches Real Repeat-Use Workflows

This makes it more than a one-shot script. It can support repeated export and format changes like a production workflow, even though the current cache granularity is not a fully independent stage-by-stage refresh interface.

### 6.5 Externalizing the Script Is a Big Token-Efficiency Win

Complex logic runs in the script while the LLM only loads orchestration rules. That is a key reason the skill is extremely token-efficient.

### 6.6 The Current Version Adds Value Not Only Through Accuracy but Through Engineering Completeness

The evaluation differences were not limited to typo correction. They also covered performance, caching, multi-format export, language normalization, and proper-noun consistency. That shows `local-transcript` is not a single-point optimization; it is a full local transcription engineering practice.

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Turning a local audio or video file into a finished transcript | Very suitable | This is the core use case |
| Chinese media transcription | Very suitable | The Chinese cleanup and proofreading path is especially strong |
| Local transcription on Apple Silicon | Very suitable | The default `mlx` path is a major advantage |
| Exporting into `txt`, `pdf`, or `docx` | Suitable | The export path is already built in |
| Repeated transcription tasks that may need reruns | Suitable | The layered cache is highly valuable |
| Cases where only a rough raw transcript is needed | Not always | The full pipeline may be heavier than necessary |
| Remote URLs or non-local files | No | The skill is scoped to local file paths |

## 8. Conclusion

The real strength of `local-transcript` is not that it can run Whisper locally once. It is that it systematizes the engineering judgments most often skipped in local transcription work: confirm the output format and dependencies first, choose the right ASR backend and mode, reduce rerun cost through layered cache reuse, then upgrade the raw recognition result into a finished transcript through simplified conversion, deterministic replacements, LLM proofreading, and proper-noun normalization, and finally explain the whole execution through structured output.

From a design perspective, the skill embodies a clear principle: **high-quality transcription is not just "recognize the words"; it is making the words fast enough, accurate enough, clean enough, and repeatable enough to become stable document output.** That is why it is especially well suited to Chinese local-media transcription and finished transcript delivery.

## 9. Document Maintenance

This document should be updated when:

- the Workflow, Format Resolution Gate, Dependency Gate, Default Behavior, Cleaning Rules, or Output Contract in `skills/local-transcript/SKILL.md` change,
- the default backend, mode presets, cache versions, LLM proofreading logic, proper-noun unification logic, output exporters, or dependency list in `skills/local-transcript/scripts/local_transcript.py` change,
- key rules in `skills/local-transcript/scripts/zh_replacements.json` or the script's built-in replacement table change,
- key supporting conclusions in `evaluate/local-transcript-skill-eval-report.md` or `evaluate/local-transcript-skill-eval-report.zh-CN.md` change.

Review quarterly; review immediately if the backend default strategy, Chinese cleanup pipeline, or caching mechanism of `local-transcript` changes substantially.

## 10. Further Reading

- `skills/local-transcript/SKILL.md`
- `skills/local-transcript/scripts/local_transcript.py`
- `skills/local-transcript/scripts/zh_replacements.json`
- `evaluate/local-transcript-skill-eval-report.md`
- `evaluate/local-transcript-skill-eval-report.zh-CN.md`
