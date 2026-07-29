#!/usr/bin/env bash
# Reproduce the two measurements AP-5 cites, so the numbers in
# references/benchmark-antipatterns.md are checkable rather than asserted.
#
#   bash scripts/gc_claim_check.sh            # full run,  ~130 MiB peak, ~30s
#   bash scripts/gc_claim_check.sh --smoke    # tiny run,  ~10 MiB peak,  ~3s
#
# Experiment 1 — a plain allocating function: does disabling GC change allocs/op?
# Experiment 2 — the same question for a sync.Pool workload, where the answer differs,
#                because Pool entries are evicted by GC (see pkg.go.dev/sync#Pool:
#                "Any item stored in the Pool may be removed automatically at any time
#                without notification").
#
# Memory budget. Experiment 2 needs GC pressure to evict pool entries, and with the
# collector off that garbage is never reclaimed — so the churn size times the iteration
# count IS the peak heap. An earlier version used 1 MiB × 3000 and reserved 3008 MiB of
# HeapSys, which is far too much to ask of a reader running a doc example. 64 KiB × 2000
# reproduces the same effect at ~130 MiB (measured, both via runtime.MemStats.HeapSys).
#
# Results are machine- and version-specific. That is the point: run it on yours.
set -euo pipefail

SMOKE=0
[[ "${1:-}" == "--smoke" ]] && SMOKE=1

# Named per mode so a tool reading these constants cannot pick up the wrong branch.
SMOKE_POOL_ITERS=200
FULL_POOL_ITERS=2000

if [[ $SMOKE -eq 1 ]]; then
  PLAIN_COUNT=1 POOL_COUNT=1 POOL_ITERS=$SMOKE_POOL_ITERS
else
  PLAIN_COUNT=5 POOL_COUNT=3 POOL_ITERS=$FULL_POOL_ITERS
fi

command -v go >/dev/null || { echo "go toolchain not found"; exit 2; }
TMP="$(mktemp -d "${TMPDIR:-/tmp}/gcclaim.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
cd "$TMP"

# Redirect the build cache into the temp dir: the default (~/Library/Caches/go-build) is
# not writable under a sandboxed run, and go then exits non-zero with
# "failed to trim cache" after having produced perfectly good results.
export GOCACHE="$TMP/.gocache" GOTOOLCHAIN=local
unset GOROOT

printf 'module gcclaim\n\ngo 1.24\n' > go.mod

cat > plain_test.go <<'EOF'
package gcclaim

import (
	"runtime/debug"
	"testing"
)

var sink []byte

func alloc() []byte { return make([]byte, 1024) }

func BenchmarkPlainGCOn(b *testing.B) {
	for i := 0; i < b.N; i++ {
		sink = alloc()
	}
}

func BenchmarkPlainGCOff(b *testing.B) {
	defer debug.SetGCPercent(debug.SetGCPercent(-1))
	for i := 0; i < b.N; i++ {
		sink = alloc()
	}
}
EOF

cat > pool_test.go <<'EOF'
package gcclaim

import (
	"runtime"
	"runtime/debug"
	"sync"
	"testing"
)

const (
	objSize  = 8 << 10  // pooled object
	garbSize = 64 << 10 // churn per iteration — this times b.N is the GC-off peak heap
)

var (
	newCalls int
	pool     = sync.Pool{New: func() any { newCalls++; return new([objSize]byte) }}
	poolSink *[objSize]byte
	garbage  []byte
)

// Allocating alongside the pool drives automatic GC, which is what evicts pool entries.
// Calling runtime.GC() explicitly would defeat the experiment: an explicit collection
// runs even when SetGCPercent(-1) has disabled the automatic one.
func poolBody() {
	p := pool.Get().(*[objSize]byte)
	poolSink = p
	pool.Put(p)
	garbage = make([]byte, garbSize)
}

func report(b *testing.B) {
	var ms runtime.MemStats
	runtime.ReadMemStats(&ms)
	b.ReportMetric(float64(newCalls), "New-calls")
	b.ReportMetric(float64(ms.HeapSys)/(1<<20), "HeapSys-MiB")
}

func BenchmarkPoolGCOn(b *testing.B) {
	newCalls = 0
	for i := 0; i < b.N; i++ {
		poolBody()
	}
	report(b)
}

func BenchmarkPoolGCOff(b *testing.B) {
	defer debug.SetGCPercent(debug.SetGCPercent(-1))
	newCalls = 0
	for i := 0; i < b.N; i++ {
		poolBody()
	}
	report(b)
}
EOF

echo "go: $(go version)"
echo

echo "── Experiment 1: plain allocating function ───────────────────────────"
echo "   expectation: B/op and allocs/op identical; ns/op far less stable with GC off"
# `set -o pipefail` is on, so a failing `go test` fails the script rather than being
# swallowed by the grep at the end of the pipe.
go test -run='^$' -bench='Plain' -benchmem -count="$PLAIN_COUNT" . \
  | grep -E '^Benchmark|^ok|^---|^FAIL'
echo

echo "── Experiment 2: sync.Pool workload ──────────────────────────────────"
echo "   expectation: 'New-calls' DROPS with GC off — pool entries are no longer evicted,"
echo "   so the code genuinely performs fewer allocations. This is why 'disabling GC cannot"
echo "   change the allocation count' is false as a general claim."
echo "   'HeapSys-MiB' is printed so the cost of the GC-off run is visible, not implied."
go test -run='^$' -bench='Pool' -benchmem -benchtime="${POOL_ITERS}x" -count="$POOL_COUNT" . \
  | grep -E '^Benchmark|^ok|^---|^FAIL'
