# Golden README Examples

Use this file as the calibration index for `readme-generator`.
It is intentionally longer than a simple file list: each example explains
why a project type routes to a specific template, what repo signals justify
that routing, and how evidence mapping should look in practice.

## Table of Contents

- [How To Use This File](#how-to-use-this-file)
- [Example 1: Go Service](#example-1-go-service)
- [Example 2: Go Library](#example-2-go-library)
- [Example 3: CLI Tool](#example-3-cli-tool)
- [Example 4: Monorepo](#example-4-monorepo)
- [Example 5: Lightweight Internal Tool](#example-5-lightweight-internal-tool)
- [Selection Heuristics](#selection-heuristics)

## How To Use This File

- Read only the example matching the detected project type.
- Treat the examples as filled-in reference shapes, not copy-paste templates.
- Every section shown below must still be grounded in real repository evidence.
- If the target repo lacks evidence for a section shown in an example, omit that
  section or mark it `Not found in repo`.

## Example 1: Go Service

### Repo signals

**Repo signals**:

- `cmd/api/main.go` exists
- `internal/` contains handlers and services
- `go.mod` declares Go `1.22`
- `.env.example` documents runtime configuration
- `.github/workflows/ci.yml` exists
- `Makefile` contains `run-api`, `test`, and `lint`
- `LICENSE` and `CONTRIBUTING.md` are present

### Template routing

- Project type: `Service`
- Selected template: `Template A: Service`
- Why: the repo exposes an application entrypoint, runtime configuration,
  deployable behavior, and service operations commands.

### Golden section order

1. Value proposition
2. Highlights
3. Prerequisites
4. Quick Start
5. End-to-end example
6. Project Structure
7. Configuration
8. Common Commands
9. Testing and Quality
10. Contributing
11. License
12. Documentation Maintenance

### Evidence mapping

| README Section | Evidence File(s) | Evidence snippet / reason |
|---|---|---|
| Overview | `cmd/api/main.go`, `internal/` | Repo is a runnable backend service |
| Quick Start | `Makefile` | `run-api` target exists |
| Configuration | `.env.example` | Runtime variables documented |
| Common Commands | `Makefile`, `.github/workflows/ci.yml` | Local and CI command paths align |
| Testing and Quality | `Makefile`, workflow YAML | `test` and `lint` are maintained |
| Contributing | `CONTRIBUTING.md` | Governance file exists |
| License | `LICENSE` | License text present |

### Notes

- Add badges when CI, coverage, Go version, and license are derivable.
- Prefer a health-check or curl example over a generic architecture diagram.
- Keep maintainer-only setup below the main quick-start path.

## Example 2: Go Library

### Repo signals

**Repo signals**:

- `go.mod` exists but no `cmd/` directory
- exported packages live under `pkg/`
- no `.env.example`
- public-facing API is code, not a server endpoint
- `.github/workflows/ci.yml` and `LICENSE` exist

### Template routing

- Project type: `Library`
- Selected template: `Template B: Library`
- Why: the core user journey is install + import + API usage, not running a service.

### Golden section order

1. Overview
2. Installation
3. Quick Usage
4. API Overview
5. Version / Compatibility Notes
6. Common Commands
7. Testing
8. License

### Evidence mapping

| README Section | Evidence File(s) | Evidence snippet / reason |
|---|---|---|
| Installation | `go.mod` | Module path and minimum Go version exist |
| Quick Usage | exported package files | Public API usage can be shown |
| API Overview | `pkg/*` | Exported symbols define the reader-facing surface |
| Testing | workflow YAML, `go test` usage in CI | Quality path is evidence-backed |
| License | `LICENSE` | License exists |

### Notes

- Do not force service-only sections like ports, env vars, or deployment.
- End-to-end command/result examples are optional here unless the library is also a generator.
- If there is no Makefile, use `go test ./...` and `go test -race ./...` from repo evidence.

## Example 3: CLI Tool

### Repo signals

**Repo signals**:

- `cmd/csvtool/main.go` exists
- help text or flag parser is in repo
- repo writes output files or emits machine-readable responses
- `Makefile` or release workflow exists
- `LICENSE` exists

### Template routing

- Project type: `CLI`
- Selected template: `Template C: CLI Tool`
- Why: the primary user action is invoking a command with flags and observing output.

### Golden section order

1. Overview
2. Installation
3. Quick Start
4. Commands
5. Flags
6. End-to-end example
7. Project Structure
8. Common Commands
9. Testing
10. License

### Evidence mapping

| README Section | Evidence File(s) | Evidence snippet / reason |
|---|---|---|
| Installation | `go.mod`, release workflow | Build/install path is defined |
| Commands | `cmd/*`, flag parser | Subcommands are real, not guessed |
| Flags | help output or parser definition | Flag names and meanings are grounded |
| End-to-end example | sample output file, tests, fixture | Input command and resulting artifact can be shown |
| Testing | workflow YAML or Makefile | Quality commands are maintained |

### Notes

- Always prefer one complete invocation over a disconnected JSON snippet.
- Show the destination file path or response shape after the command.
- If no real output example exists, show only invocation plus generic destination text.

## Example 4: Monorepo

### Repo signals

**Repo signals**:

- root `go.work` or workspace manifest exists
- `apps/` and `packages/` directories exist
- root `Makefile` orchestrates multi-module commands
- per-module READMEs exist or should exist
- root `LICENSE` may be missing

### Template routing

- Project type: `Monorepo`
- Selected template: `Template D: Monorepo`
- Why: the root README must help navigation, not replace each module's own docs.

### Golden section order

1. Overview
2. Repository Overview table
3. Quick Start
4. Shared Commands
5. Project Structure
6. Adding a New Module
7. Docs / module pointers
8. License note

### Evidence mapping

| README Section | Evidence File(s) | Evidence snippet / reason |
|---|---|---|
| Repository Overview | `apps/*`, `packages/*` | Module list and roles come from real directories |
| Shared Commands | root `Makefile` | Root orchestration targets exist |
| Project Structure | top-level tree only | Root layout can be shown without deep dumps |
| Adding a New Module | contributing docs or existing patterns | Onboarding path is evidence-backed |
| License | `LICENSE` or lack of file | If missing, say `Not found in repo` |

### Notes

- Replace deep trees with a module table.
- Link to module-level READMEs instead of embedding every submodule walkthrough.
- If `LICENSE` is absent at root, say so explicitly instead of inventing inheritance.

## Example 5: Lightweight Internal Tool

### Repo signals

**Repo signals**:

- fewer than 5 meaningful top-level directories
- no CI workflow
- no deployment path
- audience is internal contributors
- repo may be private and missing license/governance files

### Template routing

- Project type: `Lightweight`
- Selected template: `Template E: Lightweight`
- Why: a full public-style README would create more noise than clarity.

### Golden section order

1. Project overview
2. Quick Start
3. Common Commands
4. Project Structure
5. Testing
6. Documentation Maintenance

### Evidence mapping

| README Section | Evidence File(s) | Evidence snippet / reason |
|---|---|---|
| Project overview | `main.go`, small repo layout | Tool scope is narrow |
| Quick Start | direct command from repo | Simple startup path exists |
| Common Commands | native toolchain or script | No Makefile means no Makefile commands |
| Project Structure | root files/directories | Minimal shape can be explained briefly |
| Testing | test files or `go test ./...` path | Still include a quality path when evidence exists |

### Notes

- Skip badges when the repo is private or has no CI evidence.
- Skip architecture, deployment, and API reference unless the tool actually has them.
- `Not found in repo` is better than inflated completeness.

## Selection Heuristics

Use these quick checks when choosing which golden example to load:

| Signal | Route to |
|---|---|
| `cmd/api` + `.env.example` + service commands | Example 1: Go Service |
| exported packages, no `cmd/`, no runtime config | Example 2: Go Library |
| command invocation is the main product surface | Example 3: CLI Tool |
| `apps/` + `packages/` + root orchestration | Example 4: Monorepo |
| tiny private/internal repo with minimal surface | Example 5: Lightweight Internal Tool |

If a repository mixes signals:

- Prefer `Monorepo` over all others when root navigation is the dominant problem.
- Prefer `CLI` over `Library` when a user-facing executable is the main entrypoint.
- Prefer `Service` over `CLI` when runtime configuration, deployment, and operations are central.
- Use `Lightweight` only when a fuller structure would mostly duplicate empty or missing evidence.
