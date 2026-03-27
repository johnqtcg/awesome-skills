---
title: readme-generator skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# readme-generator Skill Design Rationale

`readme-generator` is a repository-evidence-driven framework for generating or refactoring README files. Its core idea is: **README work should first determine what kind of project this repository actually is, who the README is for, which commands, configuration, badges, and sections are truly supported by repository evidence, and then turn that into a maintainable, reader-friendly README while keeping evidence maps, scorecards, and degradation state out of the README body itself.** That is why the skill links Audience and Language, Project Type Routing, Evidence Completeness, Badge Detection, Command Verifiability, Navigation, End-to-End Example, and Output Contract into one explicit workflow.

## 1. Definition

`readme-generator` is used for:

- generating README files for service, library, CLI, and monorepo repositories, with a switch into lightweight mode when the triggering conditions are met,
- selecting a structure that matches the real repository shape instead of applying one generic template,
- extracting commands, configuration, structure notes, badges, and governance links from repository evidence,
- refactoring existing README files to remove fake badges, wrong config, outdated commands, and internal workflow labels,
- producing maintainable README files together with structured evidence and maintenance guidance.

Its output is not only the README text. It also includes:

- project type,
- language,
- template used,
- evidence mapping,
- scorecard,
- degraded state,
- badges added,
- sections omitted,
- and, when evidence is missing, an exact missing-evidence list.

From a design perspective, it is closer to a README-governance framework than to a prompt that merely knows how to write Markdown.

## 2. Background and Problems

The main problem this skill addresses is not that models cannot write READMEs. It is that README work naturally drifts in two damaging directions:

- filling structural gaps by guessing content,
- leaking internal workflow language into the README body.

Without explicit constraints, the most common failures cluster into eight categories:

| Problem | Typical consequence |
|---------|---------------------|
| Project type is not identified first | service, CLI, library, and monorepo repositories all get forced into the same structure |
| Evidence is not collected first | the README looks complete, but commands, config, and badges are invented or weakly supported |
| Internal workflow language leaks into the README | phrases like `Verified`, `PASS/FAIL`, or `not verified in this environment` appear in user-facing docs |
| User homepage and maintainer reference are mixed together | the README opens with setup rituals instead of project value |
| Badge generation has no discipline | fake coverage, download, or CI badges appear |
| Long READMEs have no navigation rules | CLI and complex-project READMEs become hard to scan |
| No end-to-end example is given | readers can see command syntax but not what the command actually produces |
| No maintenance triggers exist | the README drifts away from the codebase over time |

The design logic of `readme-generator` is to make "what kind of project is this, who is this README for, and what content is actually supported by repo evidence?" explicit before deciding "which sections should exist and how should they be written?"

## 3. Comparison with Common Alternatives

It helps to compare the skill with a few common alternatives:

| Dimension | `readme-generator` skill | Asking a model to "write a README" | Manually drafting a README from memory |
|-----------|--------------------------|------------------------------------|---------------------------------------|
| Project-type routing | Strong | Medium | Medium |
| Evidence completeness discipline | Strong | Weak | Weak |
| Anti-fabrication protection | Strong | Weak | Weak |
| Badge detection discipline | Strong | Weak | Weak |
| Separation between README body and process report | Strong | Weak | Weak |
| Navigation and end-to-end example rules | Strong | Weak | Medium |
| Maintenance triggers | Strong | Weak | Weak |
| Auditability of the result | Strong | Weak | Weak |

Its value is not only that it makes the README sound more polished. Its value is that it turns README creation from one-off writing into a repository-evidence documentation workflow.

## 4. Core Design Rationale

### 4.1 It Starts with the Audience and Language Gate

The first gate in `readme-generator` is not the template. It is a decision about:

- who the target readers are: contributors, operators, API consumers, or end users,
- and whether the output language should be Chinese, English, or bilingual.

This is critical because README structure, tone, and section ordering are driven by readers. A public-facing README should lead with project value and a quick start. An internal maintainer README can emphasize commands and repository structure much earlier. That is why the skill defaults to treating the top-level `README.md` as a user-facing homepage first and a maintainer reference second, unless the user explicitly asks otherwise.

### 4.2 Project Type Routing Is the Structural Axis of the Skill

The skill first classifies the repository's primary shape as:

- service/backend app,
- library/SDK,
- CLI tool,
- monorepo,

and only after that does it decide which template and section ordering to use. `lightweight` is not best understood as a peer primary type here. It is a secondary mode the skill switches into when any 2 lightweight trigger conditions are true.

This is a core design choice because README structure is not a matter of style in the abstract; it is tied directly to repository shape. Services need Quick Start, Configuration, Testing, and Project Structure. Libraries need Installation, Quick Usage, and API Overview. CLI tools depend much more on Commands and Flags plus End-to-End Examples. Monorepos need carefully limited structure views so the README does not collapse into a tree dump.

The evaluation also shows an important nuance here: project-type routing itself is not the skill's biggest unique advantage, because the base model could already classify service and CLI scenarios reasonably well. But routing is still the structural prerequisite that makes the later badge, section, example, and maintenance rules coherent.

### 4.3 The Evidence Completeness Gate Comes Before Drafting

Before drafting, `readme-generator` requires confirmation of at least:

- one entry point,
- a determined project type,
- a known command source.

It also prefers running `scripts/discover_readme_needs.sh` first.

This matters because the biggest README failure is rarely "too little was written." It is "a lot was written, but some of it was guessed." The discovery script deterministically scans for:

- `cmd/`, `pkg/`, `internal/`, `apps/`, `packages/`,
- `go.mod`, `package.json`, `pyproject.toml`, `Cargo.toml`,
- `Makefile`,
- `.github/workflows/*`,
- `.env.example`,
- governance files,
- and the current `README.md`.

It also contributes signals for:

- `go.work`, Docker-related files, config directories, and repository shape,
- license type, quality-tool presence, and repository visibility / privacy,
- `READY` vs `DEGRADED` verdicts,
- and `lightweight_candidate` routing signals.

In other words, it builds a fact table of what the repository objectively contains before deciding what the README is allowed to say. That ordering is one important reason the skill avoided fabricated content in the current evaluation.

### 4.4 It Prefers `Not found in repo` to Common-Sense Completion

One of the skill's core rules is explicit: if key information is missing, write `Not found in repo` instead of guessing.

This is one of the most important disciplines in the entire skill. In the evaluation, the without-skill refactor run introduced new fabricated content:

```markdown
docker pull acme/notification-svc:latest
```

There was no Docker evidence in the repository, but the base model still filled the gap with a generic pattern like "Go services often have Docker images." `readme-generator` is designed specifically against that kind of behavior. By requiring every non-trivial section to trace back to repository evidence, it chooses honest incompleteness over plausible fabrication.

### 4.5 The Badge Detection Gate Is Mandatory

The skill makes badge detection a required step. In the mandatory gate, it must first check:

1. CI,
2. Coverage,
3. Language version,
4. License.

In the broader Badge Strategy, the skill may also add a Release/tag badge when evidence exists.

This is very intentional because badges are one of the easiest places for README generation to look polished while still being wrong. Many READMEs casually add coverage, downloads, or release badges even when the repo has no config or derivable URL for them. The skill turns badges from decorative markdown into evidence-backed metadata through a layered detection strategy.

The evaluation shows the effect clearly: with-skill consistently produced CI + Go version + License badges across all three scenarios, while without-skill usually added only CI.

### 4.6 It Strictly Separates README Body from Process Reporting

`readme-generator` explicitly forbids the README body from containing:

- `Verified`,
- `PASS/FAIL`,
- `not verified in this environment`,
- or process wording such as "Commands are derived from the Makefile and have not been executed."

Those belong only in the assistant response through the Output Contract, Evidence Mapping, and Scorecard.

This is a clear design decision because a README is for readers, not for the documentation-generation pipeline to narrate itself. Process language inside the README harms:

- user experience,
- document longevity,
- and readability of the actual content.

So the skill explicitly splits "the README itself" from "the audit trail of how the README was produced." That separation is one of the clearest ways it differs from a generic documentation prompt.

### 4.7 The Navigation Rule and ToC Requirements Are So Specific

For longer README files, the skill requires:

- a ToC when the document is long enough,
- no inflated ToC size,
- exact consistency between ToC labels and `##` headings,
- contributor-only sections excluded from ToC by default.

Many READMEs fail not because they are factually incomplete, but because they are structurally hard to use. The Navigation Rule solves the usability problem of long documentation rather than merely the presence-or-absence problem of sections. The CLI evaluation scenario validated this directly: with-skill produced a calibrated 7-10 item ToC whose labels matched headings exactly; without-skill omitted navigation entirely.

### 4.8 The End-to-End Example Rule Matters So Much for CLI Tools

The skill explicitly prefers at least one end-to-end example for CLI tools, generators, and converters that shows:

1. the input command,
2. the resulting file name, status line, or response shape,
3. and an output snippet only when the repo contains evidence for that output.

This is valuable because many READMEs list commands without explaining what those commands actually produce. For CLI tools, the bridge between input and output is often the highest-friction part of user understanding.

Just as importantly, this rule is constrained by no-fabrication. If the repo has no sample output, the skill can describe the destination or output class, but it cannot invent a JSON or YAML body. That is exactly why the with-skill CLI scenario produced an end-to-end example without inventing output content.

### 4.9 Community and Governance Files Have Their Own Rule Set

`readme-generator` explicitly checks for:

- `LICENSE`,
- `CONTRIBUTING.md`,
- `CODE_OF_CONDUCT.md`,
- `SECURITY.md`,
- `CHANGELOG.md`.

This looks simple, but it addresses a very common README problem: many READMEs explain how to run the project but say nothing about how to contribute, how security issues are handled, or what license governs usage. The evaluation also shows an important nuance: this is not always a skill-only differentiator, because the base model can sometimes discover community files too. The gain comes from making this behavior systematic rather than incidental.

### 4.10 Output Contract, Evidence Mapping, and Maintenance Notes

One of the most distinctive parts of the skill is that it requires three separate structured outputs outside the README itself:

- Output Contract,
- Evidence Mapping,
- Documentation Maintenance.

Each solves a different problem:

- Output Contract explains which template was used, whether the result is degraded, and which badges were added,
- Evidence Mapping links each major README section back to repository files,
- Maintenance notes explain which kinds of codebase change will make the README stale.

This is also one of the clearest skill-only differences in the evaluation: all three with-skill runs produced these artifacts, and none of the without-skill runs did. In other words, the skill's true increment is not only "writing a README," but making the README result auditable, reviewable, and maintainable.

### 4.11 References Are Strongly Conditional

The references in `readme-generator` are clearly layered:

- `templates.md` supports new README generation,
- `golden-*.md` loads only for the matching project type,
- `anti-examples.md` and `checklist.md` are mainly for refactor mode,
- `command-priority.md` loads only when command sources conflict,
- `bilingual-guidelines.md` loads only for Chinese or bilingual output,
- `monorepo-rules.md` loads only for monorepo repositories.

This explains how the skill can be broad in scope without paying full token cost on every run. Core routing rules stay central, while heavier scenario-specific material loads only when the repository shape or task mode requires it.

### 4.12 Lightweight Mode Is Necessary vs. Optional Minimalism

The skill does not force the full README template onto every repository. It switches into lightweight mode when any 2 of the lightweight trigger conditions are true, such as:

- few top-level functional directories,
- no deployment or ops workflows,
- no public API or SDK surface,
- internal contributors as the primary audience.

This matters because README work can be overdesigned just as easily as it can be underdesigned. If a small repo is forced into Architecture, Deployment, API, Security, and Release sections it does not really need, the result is not richer documentation; it is noise. Lightweight mode gives the skill a structured way to choose restraint.

## 5. Problems This Design Solves

Combining the current `SKILL.md`, discovery script, key references, and evaluation report, the skill solves the following problems:

| Problem type | Corresponding design | Practical effect |
|--------------|----------------------|------------------|
| README structure does not match repository shape | Project Type Routing | Sections fit the real project type |
| Commands, config, and badges get guessed | Evidence Completeness + no-fabrication | README becomes more trustworthy |
| Internal workflow language leaks into README body | Command Verifiability Gate + hard rule | Readers see documentation, not process logs |
| Badges are fake or incomplete | Badge Detection Gate | Badges become more stable and traceable |
| Long README files are hard to scan | README Navigation Rule | Improves browsing and section discovery |
| CLI README files lack input-output bridging | End-to-End Example Rule | Usage becomes easier to understand |
| README changes are hard to audit | Evidence Mapping + Output Contract | Reviewers can verify sections more easily |
| README files go stale over time | Maintenance Note + Update Triggers | Reduces documentation drift |

## 6. Key Highlights

### 6.1 It Turns README Writing into Evidence Routing Instead of Template Filling

This is one of the deepest upgrades in the skill. It looks at repo facts first, then decides what the README is allowed to say.

### 6.2 Its Anti-Fabrication Discipline Is One of Its Biggest Strengths

The real risk in README work is often not omission, but guessing. `readme-generator` makes that risk explicit through `Not found in repo` and evidence mapping.

### 6.3 Its Separation Between README Body and Process Reporting Is a Key Differentiator

It preserves auditability while keeping `Verified`, `PASS/FAIL`, and similar process language out of the final document.

### 6.4 It Rules the Usability Layer, Not Just the Content Layer

Badges, ToC behavior, and end-to-end examples are all formalized. So the skill improves not only correctness, but also how the README is actually used.

### 6.5 Its Maintenance Notes Push README Work into a Sustainable State

This is not a one-shot deliverable. It leaves future contributors a map of which repository changes should trigger README updates.

### 6.6 Its Real Increment Is README Governance, Not Raw Markdown Ability

The evaluation already makes this clear: the base model was not terrible at classifying project type or fixing obvious stale content. The main gap was in Output Contract, Evidence Mapping, maintenance guidance, anti-fabrication, ToC discipline, and badge completeness. In other words, the skill's real value lies in documentation governance.

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Generating a README from scratch for a service, library, or CLI repo | Very suitable | Template routing and repo evidence collection are highly valuable |
| Refactoring an existing README | Very suitable | Anti-pattern detection and evidence recalibration are strong |
| Public open-source project homepage README | Very suitable | The "homepage first" principle fits well |
| Cases that need badges, ToC, and structured maintenance guidance | Suitable | These are core strengths of the skill |
| Chinese or bilingual README generation | Suitable | Bilingual rules can load on demand |
| Monorepo README generation | Suitable | But it should use the monorepo-specific rules |
| Very short internal notes | Not always | Lightweight mode may be enough, or manual writing may be simpler |

## 8. Conclusion

The real strength of `readme-generator` is not that it can produce a smooth-sounding README. It is that it systematizes the engineering judgments that README work usually skips: identify the audience and project type first, collect repository facts before drafting, decide which sections, badges, commands, and examples are actually supported by evidence, and then keep evidence mapping, scorecards, and maintenance triggers outside the README body in a structured companion output.

From a design perspective, the skill embodies a clear principle: **the key to a high-quality README is not writing every familiar section, but making sure every included section has evidence behind it, value for the reader, and a clear reason to be updated when the code changes.** That is why it is especially well suited to README generation, refactoring, and standardization work.

## 9. Document Maintenance

This document should be updated when:

- the Pre-Generation Gates, Badge Detection, Command Verifiability, Structure Policy, Navigation Rule, End-to-End Example Rule, Output Contract, or Quality Scorecard in `skills/readme-generator/SKILL.md` change,
- the project-type detection, badge-evidence detection, governance-file scanning, or degraded-mode logic in `skills/readme-generator/scripts/discover_readme_needs.sh` change,
- key rules in `skills/readme-generator/references/templates.md`, `golden-*.md`, `anti-examples.md`, `checklist.md`, `command-priority.md`, `bilingual-guidelines.md`, or `monorepo-rules.md` change,
- key supporting conclusions in `evaluate/readme-generator-skill-eval-report.md` or `evaluate/readme-generator-skill-eval-report.zh-CN.md` change.

Review quarterly; review immediately if the project-type routing, Evidence Mapping / Output Contract design, or anti-fabrication rules of `readme-generator` change substantially.

## 10. Further Reading

- `skills/readme-generator/SKILL.md`
- `skills/readme-generator/scripts/discover_readme_needs.sh`
- `skills/readme-generator/references/templates.md`
- `skills/readme-generator/references/anti-examples.md`
- `skills/readme-generator/references/golden-examples.md`
- `evaluate/readme-generator-skill-eval-report.md`
- `evaluate/readme-generator-skill-eval-report.zh-CN.md`
