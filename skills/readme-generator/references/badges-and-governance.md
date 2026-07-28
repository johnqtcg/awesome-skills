# Badges and Governance Files

Detail for SKILL.md §Badge Strategy and §Community and Governance Files. Load when
deciding which badges to emit or how to reference governance files.

## Badge Detection Order

Order of detection is also the render order.

| # | Badge | Evidence required | URL shape |
|---|-------|-------------------|-----------|
| 1 | CI status | at least one **file** in `.github/workflows/` | `![CI](https://github.com/OWNER/REPO/actions/workflows/FILE.yml/badge.svg)` |
| 2 | Coverage | `.codecov.yml` / `codecov.yml` / `.coveralls.yml`, or a Makefile `cover` target | `![Coverage](https://codecov.io/gh/OWNER/REPO/branch/BRANCH/graph/badge.svg)` |
| 3 | Language version | `go.mod` `go` directive, `package.json` `engines.node`, `pyproject.toml` `requires-python`, `Cargo.toml` `rust-version` | `![Go](https://img.shields.io/badge/Go-1.22-blue)` |
| 4 | License | `LICENSE`, `LICENSE.md`, `LICENSE.txt`, or `COPYING` | `![License](https://img.shields.io/badge/license-MIT-blue)` |
| 5 | Release | a git tag or a release workflow | `![Release](https://img.shields.io/github/v/release/OWNER/REPO)` |

`OWNER/REPO` comes from `git remote get-url origin`. If the remote is missing, skip every
badge whose URL depends on it — a badge containing the literal string `OWNER/REPO` is a
defect, and `scripts/lint_readme.py` reports it as `R005`.

## Rules

- **The directory is not the evidence.** An empty `.github/workflows/` earns no CI badge.
  `discover_readme_needs.sh` reports `ci github_actions false` in that case and adds a note.
- **The workflow filename must match.** A badge pointing at `release.yml` when only `ci.yml`
  exists renders a permanent "no status" image. Checked as `R008`.
- **Coverage config is not a coverage number.** `.codecov.yml` justifies a coverage *badge*
  and lets you state the configured *target*; it never justifies a measured percentage in
  prose. See SKILL.md §Facts vs Results.
- **Private repositories**: external badge URLs will not render for unauthorized viewers.
  Skip them and add the fallback note from SKILL.md §Badge Strategy. Detect visibility with
  `gh api repos/OWNER/REPO --jq '.private'`; the discovery script already emits
  `repo private <true|false|unknown>`.
- **Never emit a placeholder badge.** No `https://img.shields.io/badge/coverage-XX%25-green`,
  no npm download badge for a repo with no `package.json`.

## License Type Detection

Read the first five lines of whichever of `LICENSE`, `LICENSE.md`, `LICENSE.txt`, `COPYING`
exists. Match `MIT`, `Apache`, `BSD`, `ISC`, `MPL`, `Unlicense`, and the spelled-out GNU
forms — the first line of GPL-3.0 is `GNU GENERAL PUBLIC LICENSE`, which contains no
contiguous `GPL` substring, so a naive `grep GPL` misses it entirely.

| First-line match | Reported type |
|---|---|
| `GNU AFFERO GENERAL PUBLIC` | AGPL |
| `GNU LESSER GENERAL PUBLIC` | LGPL |
| `GNU GENERAL PUBLIC` | GPL |
| everything else | the matched token |

## Community and Governance File Mapping

| File | README action |
|------|---------------|
| `LICENSE` | Add a License section or badge |
| `CONTRIBUTING.md` | Add a Contributing section linking to it |
| `CODE_OF_CONDUCT.md` | Reference from the Contributing section |
| `SECURITY.md` | Add a Security section linking to it |
| `CHANGELOG.md` | Reference from the Release/Versioning section |

If `LICENSE` is missing, write:
`License: Not found in repo — consider adding a LICENSE file.`

Do not invent a license from the organization name, a sibling repository, or a package
manifest's `license` field alone — that field is a declaration, not the license text.
