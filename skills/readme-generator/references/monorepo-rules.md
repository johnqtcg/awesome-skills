# Monorepo README Rules

Load this file when `discover_readme_needs.sh` detects `project_type = monorepo` (presence of `apps/`, `packages/`, or `go.work`).

## Root README Scope

- Provide top-level overview + per-package/app quick pointers — not a full walkthrough of every module.
- Keep root README focused; link to submodule README files rather than duplicating their content.

## Required: Module Overview Table

Replace a deep directory tree with a navigation table:

```markdown
## Repository Overview

| Module | Path | Description | Docs |
|--------|------|-------------|------|
| API Server | `apps/api/` | HTTP API (Go) | [README](apps/api/README.md) |
| Worker | `apps/worker/` | Background jobs (Go) | [README](apps/worker/README.md) |
| Shared | `packages/shared/` | Common types and utils | [README](packages/shared/README.md) |
```

## Project Structure Depth Limit

- Show top-level directories only (depth 1–2 under root).
- Do not dump full file trees for every app or package — this becomes stale immediately.
- If a module's internal structure is important, put that tree in the module's own README.

## Shared Commands

Document only root-level orchestration targets (e.g., `make test`, `make build-all`, `make lint`). Per-module targets belong in each module's README.

## Adding a New Module

Include a short checklist:

```markdown
## Adding a New Module

1. Create directory under `apps/` or `packages/`
2. Add a module-level `README.md`
3. Add build/run targets to root `Makefile`
4. Update the Repository Overview table above
```

## Anti-patterns to Avoid

See `references/anti-examples.md` → "Dumping full monorepo tree" for the full BAD/GOOD pair.
