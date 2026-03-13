---
title: Best Practices for Claude Code Skills
owner: john
status: active
last_updated: 2026-03-11
applicable_versions: Claude Code 1.0+, Agent Skills Standard 1.0
---

# Best Practices for Claude Code Skills

> **Core takeaway**: A skill is an "on-demand module of specialized capability" in Claude Code. The key to a high-quality skill is not a longer prompt, but three things:
> **progressive disclosure** (three-layer loading to control context cost), **mandatory gates** (non-skippable checkpoints that constrain AI behavior), and **anti-examples** (teaching AI what *not* to do is often more effective than teaching it what to do).
> And evaluating a skill is no longer based on gut feeling. **Three-dimensional quantitative evaluation** (trigger accuracy, real task performance, and token cost-effectiveness) makes a skill's value measurable.
> This guide covers the full path from principles and design patterns to **quantitative evaluation**, real-world iteration, and integration into the development workflow, so you can build, validate, and maintain production-grade skills.

## Table of Contents

[Fundamentals.md](Fundamentals.md) (for all readers)
- Why skills exist
- A basic introduction to skills
- Deployment locations and when to use them
- Advanced structure: wrapper scripts and supporting docs
- Progressive disclosure: an elegant answer to AI context limits

[Advanced.md](Advanced.md) (for readers with some hands-on experience who want to improve quality systematically)
- Design patterns for high-quality skills
- Common pitfalls and anti-patterns
- Real-world examples: from simple to complex
- Design philosophy: from teachable knowledge to executable knowledge

[Evaluation.md](Evaluation.md) (for validating the real value of skills with data)
- Skill evaluation: quantitative validation across three dimensions
- Skills as digital assets: practice-driven continuous iteration

[Integration.md](Integration.md) (for readers who want to integrate skills into team engineering practices)
- Bringing skills into the development workflow
- How skills relate to other Claude Code features
- A cross-tool comparison of AI coding assistant customization

**Appendices**
- [Appendix A: Glossary](#appendix-a-glossary)
- [Appendix B: Maintenance Notes](#appendix-b-maintenance-notes)
- [Appendix C: Skill Quality Self-Check List](#appendix-c-skill-quality-self-check-list)
- [Appendix D: Further Reading](#appendix-d-further-reading)

---

## Appendix A: Glossary

| Term | Meaning |
|------|---------|
| **Claude Code** | Anthropic's AI coding assistant that runs in the terminal (CLI) and can read and write code, execute commands, and interact with GitHub |
| **LLM** | Large Language Model. Claude, GPT, and Gemini are all examples |
| **Context Window** | The total amount of information an LLM can "see" in a single conversation, including system instructions, chat history, file content, and more. Anything beyond the limit is truncated or forgotten |
| **Token** | The basic unit an LLM uses to process text, roughly equal to 0.75 English words or 0.5 Chinese characters. Context limits and billing are both measured in tokens |
| **Frontmatter** | The YAML metadata block between `---` lines at the top of a Markdown file. A skill uses it to define its name, description, trigger conditions, and more |
| **MCP** | Model Context Protocol. A protocol for connecting external services such as GitHub or databases to Claude Code |
| **Hook** | An event-driven automation script that runs deterministically on specific events, such as before or after a tool call, without AI decision-making |
| **Sub-agent** | A child agent that runs an isolated task in its own context window and returns the result to the main session, avoiding context bloat in the main thread |
| **Gate** | A non-skippable checkpoint inside a skill. If the condition is not met, the next step is blocked. This is different from a checklist, which can be skipped |
| **Anti-example** | A clearly documented "do not do / do not report" case inside a skill, used to suppress the AI's tendency toward false positives |

## Appendix B: Maintenance Notes

**Update this document when any of the following happens:**

1. Claude Code releases a new version with new skill-related features, such as new frontmatter fields or loading behavior
2. The Agent Skills open standard releases a new version
3. Any referenced skill scores or benchmark data in this guide changes, for example after a major skill refactor
4. Competing tools such as Cursor, Copilot, or CodeRabbit ship new features that make the comparison in this guide outdated
5. The **skill-creator evaluation framework changes** (for example, new evaluation dimensions or tooling updates), making Chapter 10 outdated

**Review cadence**: once per quarter (the skill ecosystem and AI coding assistant landscape change quickly)

---

## Appendix C: Skill Quality Self-Check List

After creating or iterating on a skill, use the checklist below to validate its quality:

| # | Check Item | Pass Criteria | Related Chapter |
|---|------------|---------------|-----------------|
| 1 | Does `description` include trigger keywords? | At least 3 highly distinctive keywords, while avoiding vague verbs | 7.1 |
| 2 | Is `SKILL.md` longer than 5,000 words? | It should not be; anything longer should be split into `references/` | 7.2, 7.9 |
| 3 | Is there at least 1 mandatory gate? | There is an explicit "stop if unmet" condition | 6.1 |
| 4 | Are there anti-examples? | At least 3 clearly defined "do not do / do not report" scenarios | 6.2 |
| 5 | Do referenced files have loading conditions? | Files in `references/` say when they should be loaded | 7.3 |
| 6 | Is the output format fixed? | Required output fields are explicitly defined | 6.5 |
| 7 | Is there version/platform awareness? | The skill reads project configuration before making recommendations | 6.6 |
| 8 | Is there a degradation strategy? | When conditions are incomplete, the skill marks the result as partial instead of pretending it is complete | 6.7 |
| 9 | Is `allowed-tools` set? | The skill limits tools according to least-privilege principles | 7.5 |
| 10 | Are there contract tests? | At minimum, structural checks exist (files present, frontmatter complete) | 6.4 |
| 11 | Has the skill been evaluated quantitatively? | Trigger accuracy is at least 90%, with data from with/without-skill comparison experiments | **10** |
| 12 | Has token cost-effectiveness been calculated? | You know the extra token cost and developer-time ROI | **10.4** |
| 13 | Does naming follow the hard constraints? | kebab-case, no reserved words, correct `SKILL.md` casing | **7.8** |
| 14 | Is the skill composable? | It does not assume exclusive control of tools/context and coexists well with other skills | **9.5** |

**How to use it**: passing at least 10 of the 14 items is acceptable; passing 13 or more is excellent. For any failed item, use the related chapter to improve it.

## Appendix D: Further Reading

- **The Complete Guide to Building Skills for Claude** — Anthropic's official skill guide (PDF), covering fundamentals, planning, testing and iteration, distribution, patterns, and troubleshooting
- [Agent Skills Open Standard](https://agentskills.io/) — the cross-platform standard skills follow
- [Claude Code Skills Documentation](https://docs.anthropic.com/en/docs/claude-code/skills) — the official guide to using skills
- [What Are Skills](https://claude.com/resources/tutorials/what-are-skills) — official tutorial: a basic introduction to skills
- [How Skills Compare to Other Features](https://claude.com/resources/tutorials/how-skills-compare-to-other-claude-code-features) — official tutorial: skills compared with other features
- [anthropics/skills](https://github.com/anthropics/skills) — Anthropic's official skill repository with customizable example skills
- [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) — Anthropic's official skill evaluation framework (`evals.json` / `run_eval.py` / `run_loop.py` / `generate_review.py`)
- [go-code-reviewer-skill-eval-report.zh-CN.md](../../evaluate/go-code-reviewer-skill-eval-report.zh-CN.md) — the three-dimensional evaluation report for the `go-code-reviewer` skill (the data source for the Chapter 10 case study)
