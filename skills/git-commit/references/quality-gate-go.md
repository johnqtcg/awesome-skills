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

## Static Analysis

- **<= 20 packages**: `go vet ./...`
- **> 20 packages**: `go vet $CHANGED_PKGS` (scope to changed packages only)

## Tests

- **<= 20 packages**: `go test ./...`
- **> 20 packages**: `go test $CHANGED_PKGS`

Note: POSIX shell utilities required (`dirname`, `sort`, `sed`). On native Windows without Git Bash/WSL, list changed packages manually.
