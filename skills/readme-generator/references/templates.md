# README Templates by Project Type

Each template is a fillable markdown skeleton. Replace `{PLACEHOLDER}` with repo evidence.
Remove sections marked `<!-- optional -->` if not applicable.

**Structure here, commands elsewhere.** These skeletons define *which sections* a project
type needs. The command bodies are placeholders — `{INSTALL_CMD}`, `{TEST_CMD}`,
`{VERSION_LINE}` — resolved from `references/language-snippets.md` according to the manifest
the repo actually has. Baking `go install` into "Template C" made every Node, Python, and
Rust CLI a rewrite rather than a fill-in.

Resolve the two axes independently:

| Axis | Source |
|---|---|
| Which sections, in what order | `project_type effective` from `discover_readme_needs.sh` → the template below |
| What the commands say | the manifest present in the repo → `language-snippets.md` |

**Every skeleton here satisfies the required-section matrix for its type** (SKILL.md
§Structure Policy). That is checked mechanically by
`scripts/tests/test_skill_contract.py::TestTemplateRequiredSections`, so a template cannot
drift into telling you to omit a section the skill requires. The reverse also holds: a type
whose matrix row lists Configuration has it below; one whose row does not, does not.

## Prerequisites Section Format (CLI / Service)

List required runtime dependencies first, then optional ones. State the version constraint,
the purpose, and a setup link when non-trivial.

```markdown
## Prerequisites

- Go `>= 1.21` ([download](https://go.dev/dl/))
- A GitHub Personal Access Token with `repo` read permission ([create one](https://github.com/settings/tokens))
- _(Optional)_ An OpenAI API key — required only for the AI summary feature
- _(Optional)_ Docker — required only for `make docker-build`
```

---

## Template A: Service / Backend

````markdown
<!-- badges: auto-detect from CI/coverage/go.mod -->
![CI]({CI_BADGE_URL})
![Coverage]({COVERAGE_BADGE_URL})
![Go Version]({GO_VERSION_BADGE})

# {PROJECT_NAME}

{One-sentence description of what this service does and its primary value.}

## Quick Start

### Prerequisites

- {VERSION_LINE} (from the language manifest)
- {DATABASE/DEPENDENCY} (only when a config file proves the dependency)
- Environment variables (see [Configuration](#configuration))

### Run

```bash
{SETUP_CMD}     # e.g. cp .env.example .env, make install-tools
{RUN_CMD}       # start the service
```

## Project Structure

| Path | Purpose |
|------|---------|
| `{ENTRYPOINT_DIR}` | Server entrypoint |
| `{HANDLER_DIR}` | Request handlers |
| `{SERVICE_DIR}` | Business logic |
| `{DATA_DIR}` | Data access layer |
| `{CONFIG_DIR}` | Configuration |

List only directories that exist. `cmd/` + `internal/` is a Go convention, `src/` is
Node/Python, `crates/` is a Rust workspace — use the repository's own layout.

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `{ENV_VAR_1}` | Yes | — | {Description} |
| `{ENV_VAR_2}` | No | `{DEFAULT}` | {Description} |

Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
```

## Common Commands

```bash
{BUILD_CMD}
{RUN_CMD}
{TEST_CMD}
{LINT_CMD}
```

> Command source: {Makefile / package.json / native toolchain}.

## Testing and Quality

```bash
{TEST_CMD}
{LINT_CMD}
```

State a coverage target only when a config file commits one (`.codecov.yml`, a Makefile
threshold). A measured percentage is not a repository fact — SKILL.md §Facts vs Results.

<!-- optional: Architecture -->
## Architecture

{Brief description of service architecture, data flow, key design decisions. Include diagram if evidence exists.}

<!-- optional: Deployment -->
## Deployment

{Deployment target, process, and commands. Only if deployment config exists in repo.}

<!-- optional: API -->
## API Documentation

{Link to Swagger/OpenAPI docs if swagger target exists. E.g., `make swagger` generates docs at `docs/swagger/`.}

## Documentation Maintenance

This README should be updated when:
- New entrypoints are added under `cmd/`
- Environment variables change
- Makefile targets are added or renamed
- CI workflows change

## License

{License type from LICENSE file, or "Not found in repo — consider adding a LICENSE file."}
````

---

## Template B: Library / SDK

````markdown
![CI]({CI_BADGE_URL})
![Go Version]({GO_VERSION_BADGE})
![License]({LICENSE_BADGE})

# {PACKAGE_NAME}

{One-sentence description of what this library provides.}

## Installation

```bash
{LIB_INSTALL_CMD}
```

## Quick Usage

```{LANG}
{IMPORT_LINE}

// {minimal working example — 5-15 lines, taken from a test or example file}
```

## API Overview

| Function/Type | Description |
|--------------|-------------|
| `{Func1}` | {One-line description} |
| `{Func2}` | {One-line description} |
| `{Type1}` | {One-line description} |

For the full API reference, see {API_DOC_URL} (pkg.go.dev / docs.rs / the published docs
site — only when the package is actually published there).

## Compatibility

- {VERSION_LINE} (from the language manifest)
- {Other compatibility notes}

## Testing

```bash
{TEST_CMD}
```

<!-- optional: Contributing -->
## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

{License type from LICENSE file, or "Not found in repo — consider adding a LICENSE file."}

## Documentation Maintenance

Update this README when:
- the exported API surface changes
- the minimum language version in the manifest changes
- new built-in rules or options are added
````

---

## Template C: CLI Tool

````markdown
![CI]({CI_BADGE_URL})
![Go Version]({GO_VERSION_BADGE})

# {CLI_NAME}

{One-sentence description of what this CLI does.}

## Installation

```bash
{INSTALL_CMD}

# or build from source
{BUILD_CMD}
```

## Usage

```bash
# basic usage
{CLI_NAME} {SUBCOMMAND} [flags]

# examples
{CLI_NAME} convert --input file.txt --output result.md
{CLI_NAME} serve --port 8080
```

## Commands and Flags

| Command | Description |
|---------|-------------|
| `{cmd1}` | {Description} |
| `{cmd2}` | {Description} |

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--{flag1}` | `-{f}` | `{default}` | {Description} |
| `--{flag2}` | `-{f}` | `{default}` | {Description} |

<!-- optional: Configuration — only when the CLI reads a config file or env vars.
     A flag table is not configuration; do not add this section just to fill space. -->
## Configuration

{CLI_NAME} reads configuration from (in priority order):
1. Command-line flags
2. Environment variables (`{PREFIX}_*`)
3. Config file (`{config_path}`)

<!-- optional: Exit Codes -->
## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| {N} | {Specific error} |

## Development and Testing

```bash
{BUILD_CMD}
{TEST_CMD}
{LINT_CMD}
```

> Command source: {Makefile / package.json / native toolchain}.

## License

{License type from LICENSE file, or "Not found in repo — consider adding a LICENSE file."}

## Documentation Maintenance

Update this README when:
- subcommands or flags are added, renamed, or removed
- output formats change
- the install path changes
````

---

## Template D: Monorepo

````markdown
![CI]({CI_BADGE_URL})

# {PROJECT_NAME}

{One-sentence description of the overall project/organization.}

## Repository Overview

| Module | Path | Description | Docs |
|--------|------|-------------|------|
| {Mod1} | `{MODULE_ROOT}/{mod1}/` | {One-line description} | [README]({MODULE_ROOT}/{mod1}/README.md) |
| {Mod2} | `{MODULE_ROOT}/{mod2}/` | {One-line description} | [README]({MODULE_ROOT}/{mod2}/README.md) |

## Quick Start

```bash
{SETUP_CMD}         # install shared tooling
{RUN_CMD}           # run one module, e.g. make run-{app1} / cargo run -p {app1}
{TEST_CMD}          # test everything
```

## Shared Commands

```bash
{HELP_CMD}              # list available targets, when the repo has one
{BUILD_CMD}             # build every module
{TEST_CMD}              # test every module
{LINT_CMD}              # lint every module
```

> Command source: {root Makefile / workspace tool / native toolchain}.

## Project Structure

| Path | Contents |
|------|----------|
| `{MODULE_ROOT}/{mod1}` | {Description} — see its own README |
| `{MODULE_ROOT}/{mod2}` | {Description} — see its own README |
| `{WORKSPACE_MANIFEST}` | Workspace definition |

`{MODULE_ROOT}` is whatever the repo uses: `apps/` and `packages/` (npm workspaces,
`go.work`), `crates/` (Cargo workspace), `services/`, or a flat root. Read it from the
discovery output rather than assuming — `discover_readme_needs.sh` emits one
`entrypoint module <path>` line per module it found.

## Adding a New Module

1. Create the directory under `{MODULE_ROOT}/`
2. Register it in `{WORKSPACE_MANIFEST}` (`go.work use`, Cargo `members`, npm
   `workspaces`) — omit this step if the workspace globs its members
3. Add a module-level `README.md`
4. Wire it into the shared command source, if the repo has one
5. Update the Repository Overview table above

## Testing

```bash
{TEST_CMD}              # every module
{TEST_ONE_CMD}          # a single module, when the tooling supports it
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow.

## License

{License type from LICENSE file, or "Not found in repo — consider adding a LICENSE file."}

## Documentation Maintenance

Update this README when:
- a module is added to or removed from the workspace
- the shared command set changes
- the workspace manifest changes
````

---

## Template E: Lightweight (Small/Internal Repos)

Use this when the repository is small and heavy sections would add maintenance burden.

````markdown
# {PROJECT_NAME}

{One-sentence summary of purpose.}

## Quick Start

```bash
{PRIMARY_RUN_COMMAND}
```

> Command source: {Makefile/package.json/go commands}.

## Common Commands

```bash
{BUILD_CMD}
{TEST_CMD}
{LINT_CMD}
```

> Resolve these from `language-snippets.md` using the repo's manifest.

## Project Structure

```
{PROJECT_NAME}/
├── {KEY_DIR_1}/   # {purpose}
├── {KEY_DIR_2}/   # {purpose}
└── {ENTRYPOINT}   # {purpose}
```

## Testing and Quality

- Test: `{TEST_CMD}`
- Lint: `{LINT_CMD}`
- Coverage: `{COVER_CMD | Not found in repo}`

## Documentation Maintenance

Update this README when:
- commands change
- entrypoints change
- required config/env changes
````

---

## Resolving Placeholders

| Placeholder | Resolve from |
|---|---|
| `{INSTALL_CMD}` `{LIB_INSTALL_CMD}` `{BUILD_CMD}` `{RUN_CMD}` `{TEST_CMD}` `{LINT_CMD}` `{VERSION_LINE}` | `language-snippets.md`, keyed by the manifest in the repo |
| `{SETUP_CMD}` `{HELP_CMD}` `{TEST_ONE_CMD}` | the Makefile/script/workspace tool the repo actually has; omit the line when it has none |
| `{MODULE_ROOT}` `{WORKSPACE_MANIFEST}` | the module parent (`apps/`, `packages/`, `crates/`, `services/`) and manifest (`go.work`, `Cargo.toml`, `package.json`) that discovery reported |
| `{ENTRYPOINT_DIR}` and the other structure rows | directories that actually exist |
| `{API_DOC_URL}` | only when the package is published to that docs host |
| `{PROJECT_NAME}` `{MODULE_PATH}` `{CLI_NAME}` | the manifest |

An unresolved `{PLACEHOLDER}` shipped in a README is a defect — `lint_readme.py` reports it
as R005. If a placeholder has no evidence behind it, delete the line rather than guessing.
