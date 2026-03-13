---
title: Contributing Guide
owner: john
status: active
last_updated: 2026-03-13
applicable_versions: repository layout as of 2026-03
---

# Contributing Guide

Thanks for contributing to `awesome-skills`.

This repository is built around **skill methodology, skill assets, review reports, and output examples**. When contributing, prioritize content quality, structural completeness, verifiability, and Chinese/English consistency.

Language:
- English: `CONTRIBUTING.md`
- Chinese: [CONTRIBUTING.zh-CN.md](/Users/john/awesome-skills/CONTRIBUTING.zh-CN.md)

## 1. Principles

Please keep contributions aligned with these goals:

- make the methodology in `bestpractice/` clearer, more systematic, and more actionable
- make the examples in `skills/` higher quality and more reusable
- make the reviews in `evaluate/` more specific and evidence-based
- make the examples in `outputexample/` better proof of real skill value

Core expectations:

- follow the existing repository structure instead of importing unrelated engineering templates
- explain `What / Why / How`, not just the final result
- prefer contributions that can be checked or validated
- keep Chinese and English content aligned to avoid one side going stale

## 2. What You Can Contribute

This repository welcomes contributions such as:

1. improving the methodology docs in `bestpractice/`
2. adding or refactoring high-quality skills in `skills/`
3. adding or correcting review reports in `evaluate/`
4. adding or updating output examples in `outputexample/`
5. fixing README files, navigation, links, or bilingual sync issues
6. correcting factual errors, unclear wording, or weak examples in the docs

## 3. Repository Structure

Please understand the four core directories first:

| Path | Purpose |
| --- | --- |
| [bestpractice/](/Users/john/awesome-skills/bestpractice) | Skill best-practice docs, in Chinese and English |
| [skills/](/Users/john/awesome-skills/skills) | High-quality skill examples |
| [evaluate/](/Users/john/awesome-skills/evaluate) | Skill review reports, in Chinese and English |
| [outputexample/](/Users/john/awesome-skills/outputexample) | Real output examples from skills |

## 4. Preferred Contribution Unit

If you are adding a new high-quality skill, the preferred submission unit is a complete package rather than a single isolated `SKILL.md`:

1. `skills/<skill-name>/SKILL.md`
2. at least one review report:
   - `evaluate/<skill-name>-skill-eval-report.zh-CN.md`
   - `evaluate/<skill-name>-skill-eval-report.md`
3. at least one output example directory:
   - `outputexample/<skill-name>/`

This is not a hard mechanical rule, but it matches how the repository is currently organized and gives the strongest contribution quality.

## 5. Naming and Organization Rules

Follow the naming patterns already used in the repository:

- skill directory names use `kebab-case`
- the main skill file is always `SKILL.md`
- review report filenames use:
  - `<skill-name>-skill-eval-report.md`
  - `<skill-name>-skill-eval-report.zh-CN.md`
- output example directories usually use the same name as the skill:
  - `outputexample/<skill-name>/`

If you change bilingual docs, update both language versions together whenever possible, for example:

- `README.md` and `README.zh-CN.md`
- `CONTRIBUTING.md` and `CONTRIBUTING.zh-CN.md`
- `bestpractice/*.md` and their English counterparts

## 6. Documentation and Content Quality

Before opening a PR, check at least these points:

1. the document structure is clear and the entry points are easy to find
2. terminology is consistent throughout
3. Markdown links and paths are valid
4. Chinese and English versions have not drifted apart
5. for new skills, the description, gates, anti-examples, and output contract are complete
6. for new review reports, include evidence and reasoning instead of just saying “good” or “bad”
7. for new output examples, filenames and directory structure should remain clear and traceable

## 7. Suggested Checks Before You Submit

Before contributing, at minimum run these repository-level checks:

```bash
find skills -maxdepth 2 -name SKILL.md | sort
find evaluate -maxdepth 1 -type f | sort
find outputexample -maxdepth 2 -type f | sort
sed -n '1,200p' README.zh-CN.md
sed -n '1,200p' README.md
git diff --check
```

If you are adding a skill, also verify that its supporting files are present:

```bash
find "skills/<skill-name>" -maxdepth 2 -type f | sort
find evaluate -maxdepth 1 -type f | rg "<skill-name>"
find outputexample -maxdepth 2 -type f | rg "<skill-name>"
```

## 8. Branch and Commit Suggestions

Suggested branch names:

- `feature/<topic>`
- `docs/<topic>`
- `fix/<topic>`
- `chore/<topic>`

Suggested commit message format:

```text
<type>(<scope>): <subject>
```

Examples:

```text
docs(readme): reorganize skill categories
feat(skill): add thirdparty api integration example
fix(bestpractice): correct broken section links
```

## 9. Pull Request Expectations

In your PR description, try to include:

- background and goal
- the main changes
- why this change was made
- if the change adds a skill: where the review report and output example live
- if the change touches bilingual docs: whether both language versions were updated

Suggested PR checklist:

- [ ] The change fits the repository model: methodology + skill + review + output example
- [ ] Relevant Markdown links and paths are valid
- [ ] Chinese and English content is updated together, or the reason is explained
- [ ] If a new skill was added, a matching review and output example were added, or the gap is explicitly explained
- [ ] README or navigation docs were updated when needed

## 10. Security and Responsible Disclosure

Repository governance documents:

- Security:
  - [SECURITY.md](/Users/john/awesome-skills/SECURITY.md)
  - [SECURITY.zh-CN.md](/Users/john/awesome-skills/SECURITY.zh-CN.md)
- Code of Conduct:
  - [CODE_OF_CONDUCT.md](/Users/john/awesome-skills/CODE_OF_CONDUCT.md)
  - [CODE_OF_CONDUCT.zh-CN.md](/Users/john/awesome-skills/CODE_OF_CONDUCT.zh-CN.md)

If your contribution involves:

- exploitable security issues
- credentials, keys, or sensitive data
- content that could mislead users into unsafe actions

do not publish exploit details directly in a public Issue or PR. Share only the minimum needed to explain the problem, then coordinate the next step with the maintainer.

## 11. Maintenance Notes

Please update this guide when any of the following changes:

1. the repository structure changes
2. core directories are added or removed
3. naming conventions for skills, reviews, or output examples change
4. the bilingual documentation maintenance policy changes
