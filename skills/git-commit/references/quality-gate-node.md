# Quality Gate: Node.js / TypeScript

Marker: `package.json` in the repo root.

## Package Manager Detection

Pick the first match: `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `package-lock.json` or none → npm. Abbreviate as `<pm>` below.

## Lint

If `package.json` has a `"lint"` script: `<pm> run lint`.

## Type Check

If `tsconfig.json` exists: `<pm> exec tsc --noEmit`, or `<pm> run typecheck` if a `"typecheck"` script is defined. (Note: use `exec` not `run` for direct binary invocation — `run` executes named scripts, and npm `run` swallows flags after the script name.)

## Tests

Determine scope by counting source files:

```bash
FILE_COUNT=$(git diff --cached --name-only -- '*.js' '*.ts' '*.jsx' '*.tsx' | wc -l | tr -d ' ')
```

- **<= 50 changed files AND no workspace monorepo**: `<pm> test`.
- **> 50 changed files OR workspace monorepo detected** (`workspaces` field in `package.json`, or `nx.json`, `turbo.json`, `lerna.json` exists):
  - **Workspace-aware tools (preferred)**:
    - nx: `npx nx affected --target=test --base=HEAD` (compares staged changes against current HEAD)
    - turborepo: `npx turbo run test --filter=...[HEAD]`
    - lerna: `npx lerna run test --since=HEAD`
  - **Manual path filtering** (if no workspace tool):
    ```bash
    CHANGED_DIRS=$(git diff --cached --name-only -- '*.js' '*.ts' '*.jsx' '*.tsx' \
      | while read -r f; do dirname "$f"; done \
      | sort -u)
    # Jest
    <pm> test -- $CHANGED_DIRS
    # Vitest
    <pm> exec vitest run $CHANGED_DIRS
    ```
- If no `"test"` script exists in `package.json`, skip and note it.