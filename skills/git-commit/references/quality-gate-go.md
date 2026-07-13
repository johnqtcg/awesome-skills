# Quality Gate: Go

Marker: `go.mod` in the repo root (or nearest parent of staged `.go` files).

## Scope Detection

```bash
PKG_COUNT=$(go list ./... | wc -l | tr -d ' ')
CHANGED_PKGS=$(git diff --cached --name-only -- '*.go' \
  | while read -r f; do dirname "$f"; done \
  | sort -u \
  | sed 's|^|./|')
```

## Build

- **<= 20 packages**: `go build ./...`
- **> 20 packages**: `go build $CHANGED_PKGS`

## Static Analysis

- Prefer `golangci-lint run` when available and configured for the repo.
- **<= 20 packages**: `go vet ./...`
- **> 20 packages**: `go vet $CHANGED_PKGS` (scope to changed packages only)

## Tests

- **<= 20 packages**: `go test ./...`
- **> 20 packages**: still prefer `go test ./...` — Go caches unchanged packages
  (`ok ... (cached)`), so a full run is usually cheap, and unlike scoping to
  `$CHANGED_PKGS` it **cannot miss a reverse dependency** (a package that imports a
  changed one). Scope to `$CHANGED_PKGS` only when a full run is proven too slow, and
  then state explicitly that reverse-dependency tests were skipped.

Note: POSIX shell utilities required (`dirname`, `sort`, `sed`). On native Windows without Git Bash/WSL, list changed packages manually.
