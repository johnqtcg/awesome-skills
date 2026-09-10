#!/usr/bin/env bash
# Build five realistic Go repos for a live task evaluation of go-makefile-writer.
# Each is a genuine repo: it compiles, its tests pass, and its shape is one the
# skill's project-shape table claims to handle.
set -eu
ROOT="${1:?usage: mkfixtures.sh <dir>}"
mkdir -p "$ROOT"

# ---------------------------------------------------------------- 1. monorepo
# go.work with two members; only one has programs, and one program's file is
# NOT called main.go. A `cmd/**/main.go` glob gets this wrong twice.
R="$ROOT/monorepo"; mkdir -p "$R/svc-api/cmd/api" "$R/svc-api/cmd/worker" "$R/pkglib"
cat > "$R/go.work" <<'EOF'
go 1.22

use (
	./svc-api
	./pkglib
)
EOF
cat > "$R/svc-api/go.mod" <<'EOF'
module example.com/svc-api

go 1.22
EOF
cat > "$R/svc-api/cmd/api/entry.go" <<'EOF'
package main

import "fmt"

var version = "dev"

func main() { fmt.Println("api", version) }
EOF
cat > "$R/svc-api/cmd/worker/main.go" <<'EOF'
package main

import "fmt"

func main() { fmt.Println("worker") }
EOF
mkdir -p "$R/svc-api/internal/queue"
cat > "$R/svc-api/internal/queue/main.go" <<'EOF'
package queue

// A non-main package in a file called main.go — a filename glob reports it.
func Depth() int { return 0 }
EOF
cat > "$R/pkglib/go.mod" <<'EOF'
module example.com/pkglib

go 1.22
EOF
cat > "$R/pkglib/strs.go" <<'EOF'
package pkglib

func Upper(s string) string {
	b := []byte(s)
	for i := range b {
		if b[i] >= 'a' && b[i] <= 'z' {
			b[i] -= 32
		}
	}
	return string(b)
}
EOF
cat > "$R/pkglib/strs_test.go" <<'EOF'
package pkglib

import "testing"

func TestUpper(t *testing.T) {
	if Upper("ab") != "AB" {
		t.Fatal("bad")
	}
}
EOF

# ------------------------------------------------------------- 2. library only
R="$ROOT/library"; mkdir -p "$R/retry" "$R/cmd/internal"
cat > "$R/go.mod" <<'EOF'
module example.com/retry

go 1.22
EOF
cat > "$R/retry/retry.go" <<'EOF'
package retry

import "errors"

var ErrExhausted = errors.New("attempts exhausted")

func Do(attempts int, fn func() error) error {
	var last error
	for i := 0; i < attempts; i++ {
		if last = fn(); last == nil {
			return nil
		}
	}
	if last == nil {
		return ErrExhausted
	}
	return last
}
EOF
cat > "$R/retry/retry_test.go" <<'EOF'
package retry

import "testing"

func TestDoSucceeds(t *testing.T) {
	if err := Do(3, func() error { return nil }); err != nil {
		t.Fatal(err)
	}
}
EOF
# A decoy: a file named main.go that is NOT package main.
cat > "$R/cmd/internal/main.go" <<'EOF'
package internal

func Helper() {}
EOF

# --------------------------------------------------------------------- 3. cgo
R="$ROOT/cgoproj"; mkdir -p "$R/cmd/hasher"
cat > "$R/go.mod" <<'EOF'
module example.com/cgoproj

go 1.22
EOF
cat > "$R/cmd/hasher/main.go" <<'EOF'
package main

/*
#include <stdlib.h>
static int twice(int x) { return x * 2; }
*/
import "C"

import "fmt"

var version = "dev"

func main() { fmt.Println("hasher", version, int(C.twice(21))) }
EOF
cat > "$R/hash.go" <<'EOF'
package cgoproj

func Sum(a, b int) int { return a + b }
EOF
cat > "$R/hash_test.go" <<'EOF'
package cgoproj

import "testing"

func TestSum(t *testing.T) {
	if Sum(1, 2) != 3 {
		t.Fatal("bad")
	}
}
EOF

# ------------------------------------------------- 4. existing complex Makefile
R="$ROOT/refactor"; mkdir -p "$R/cmd/server" "$R/cmd/migrate" "$R/internal/store"
cat > "$R/go.mod" <<'EOF'
module example.com/legacy

go 1.22
EOF
cat > "$R/cmd/server/main.go" <<'EOF'
package main

import "fmt"

var version = "dev"

func main() { fmt.Println("server", version) }
EOF
cat > "$R/cmd/migrate/main.go" <<'EOF'
package main

import "fmt"

func main() { fmt.Println("migrate") }
EOF
cat > "$R/internal/store/store.go" <<'EOF'
package store

func Get(k string) string { return k }
EOF
cat > "$R/internal/store/store_test.go" <<'EOF'
package store

import "testing"

func TestGet(t *testing.T) {
	if Get("a") != "a" {
		t.Fatal("bad")
	}
}
EOF
# The pre-existing Makefile: idiosyncratic names CI depends on, no help target,
# no .PHONY, a pipeline that swallows failure, and no -race.
cat > "$R/Makefile" <<'MAKEEOF'
GO=go
OUT=build

compile:
	mkdir -p $(OUT)
	$(GO) build -o $(OUT)/server ./cmd/server
	$(GO) build -o $(OUT)/migrate ./cmd/migrate

unit:
	$(GO) test ./...

vet:
	$(GO) vet ./... | tee vet.log

wipe:
	rm -rf $(OUT) vet.log
MAKEEOF
mkdir -p "$R/.github/workflows"
cat > "$R/.github/workflows/ci.yml" <<'EOF'
name: ci
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: '1.22'
      - run: make unit
      - run: make vet
      - run: make compile
EOF

# -------------------------------------------------- 5. plain single-module app
R="$ROOT/single"; mkdir -p "$R/internal/calc"
cat > "$R/go.mod" <<'EOF'
module example.com/single

go 1.22
EOF
cat > "$R/main.go" <<'EOF'
package main

import "fmt"

var version = "dev"

func main() { fmt.Println("single", version) }
EOF
cat > "$R/internal/calc/calc.go" <<'EOF'
package calc

func Add(a, b int) int { return a + b }
EOF
cat > "$R/internal/calc/calc_test.go" <<'EOF'
package calc

import "testing"

func TestAdd(t *testing.T) {
	if Add(1, 1) != 2 {
		t.Fatal("bad")
	}
}
EOF

for d in "$ROOT"/*/; do
  ( cd "$d" && git init -q . && git config user.email e@e.com && git config user.name t \
      && git add -A && git commit -qm init ) >/dev/null
done
echo "fixtures in $ROOT"
ls "$ROOT"
