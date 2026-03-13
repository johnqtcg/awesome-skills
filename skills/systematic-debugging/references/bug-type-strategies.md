# Bug Type Strategies

## Table of Contents

1. [Overview](#overview)
2. [Logic Errors / Wrong Output](#1-logic-errors--wrong-output)
3. [Race Conditions / Concurrency Bugs](#2-race-conditions--concurrency-bugs)
4. [Memory Leaks / Performance Regression](#3-memory-leaks--performance-regression)
5. [Environment / Configuration Bugs](#4-environment--configuration-bugs)
6. [Third-Party Dependency Changes](#5-third-party-dependency-changes)
7. [Build / Compilation Errors](#6-build--compilation-errors)
8. [Decision Flowchart](#decision-flowchart)

## Overview

Different bug types require different investigation approaches. Using the wrong strategy wastes time — profiling a logic error or reading code to find a race condition are both ineffective.

**Use this reference** to pick the right Phase 1 strategy based on bug symptoms.

## 1. Logic Errors / Wrong Output

**Symptoms:** Code runs without errors but produces wrong results.

**Strategy:** Trace data flow backward from wrong output to wrong input.

**Primary technique:** `references/root-cause-tracing.md`

**Example (Go):**
```go
// Bug: calculateDiscount returns 0 for premium users
// Symptom: discount == 0 when user.Tier == "premium"

// Step 1: Where is discount calculated?
func calculateDiscount(user User, total float64) float64 {
    if user.Tier == "Premium" {  // <-- Case-sensitive comparison!
        return total * 0.15
    }
    return 0
}

// Step 2: What value comes in?
// user.Tier = "premium" (lowercase from database)

// Root cause: Case mismatch between DB value and code check
// Fix: strings.EqualFold(user.Tier, "Premium")
```

**Key tools:** Debugger, strategic print/log statements, unit test with actual values.

## 2. Race Conditions / Concurrency Bugs

**Symptoms:** Flaky tests, intermittent failures, "works on my machine", failures under load.

**Strategy:** Identify shared mutable state, then prove the race exists.

**Do NOT:** Add sleep/retry as first instinct. That masks the race.

**Example (Go):**
```go
// Bug: map concurrent write panic in production, never in dev
// Symptom: "fatal error: concurrent map writes" under load

// Step 1: Find the shared state
var cache = make(map[string]*Result)  // package-level, no mutex

// Step 2: Find concurrent access points
func HandleRequest(w http.ResponseWriter, r *http.Request) {
    key := r.URL.Path
    if result, ok := cache[key]; ok {  // concurrent read
        json.NewEncoder(w).Encode(result)
        return
    }
    result := computeExpensive(key)
    cache[key] = result  // concurrent write - RACE!
    json.NewEncoder(w).Encode(result)
}

// Step 3: Prove it
// go test -race ./...
// go run -race ./cmd/server

// Root cause: Unprotected shared map
// Fix: sync.RWMutex or sync.Map
```

**Key tools:**
- Go: `go test -race ./...`, `go run -race`
- Python: `threading` module debug, `asyncio.get_event_loop().set_debug(True)`
- General: Thread sanitizer, stress tests with high concurrency

## 3. Memory Leaks / Performance Regression

**Symptoms:** Gradually increasing memory/CPU, slow responses over time, OOM kills.

**Strategy:** Profile FIRST, hypothesize SECOND. Never guess at performance.

**Example (Go):**
```go
// Bug: Service memory grows 50MB/hour, OOM after 8 hours
// Symptom: Kubernetes pod restarts every ~8h

// Step 1: Profile (don't guess!)
import _ "net/http/pprof"
// curl http://localhost:6060/debug/pprof/heap > heap.prof
// go tool pprof heap.prof
// (pprof) top 10

// Step 2: Profile reveals:
//   80% of allocations from processEvent()
//   Specifically: subscribers slice grows unbounded

func (b *Broker) processEvent(event Event) {
    b.subscribers = append(b.subscribers, event.callback)
    // Never removed! Subscribers accumulate forever.
}

// Root cause: Missing cleanup of expired subscribers
// Fix: Add subscriber TTL and periodic cleanup
```

**Key tools:**
- Go: `pprof` (CPU/memory/goroutine), `runtime.MemStats`, `trace`
- Python: `tracemalloc`, `memory_profiler`, `cProfile`
- Node.js: `--inspect` + Chrome DevTools, `clinic.js`
- General: `top`/`htop`, Grafana dashboards, load testing with `k6`/`wrk`

## 4. Environment / Configuration Bugs

**Symptoms:** "Works on my machine", passes locally fails in CI, works in staging not production.

**Strategy:** Systematically diff environments layer by layer.

**Example (Python):**
```python
# Bug: API works locally, returns 500 in Docker
# Symptom: "ModuleNotFoundError: No module named 'pandas'"

# Step 1: Compare environments
# Local:  python 3.11.5, pip 23.2, pandas 2.1.0
# Docker: python 3.11.5, pip 23.2, pandas NOT INSTALLED

# Step 2: Check dependency files
# requirements.txt has: pandas==2.1.0
# But Dockerfile installs from: requirements-base.txt (missing pandas)

# Step 3: Trace the divergence
# Dockerfile line 12: COPY requirements-base.txt .
# Should be:          COPY requirements.txt .

# Root cause: Wrong requirements file in Dockerfile
# Fix: Update COPY instruction
```

**Investigation checklist:**
```
For EACH difference between working and broken environments, check:
[ ] Language/runtime version
[ ] Dependency versions (lock file vs installed)
[ ] Environment variables (present? correct values?)
[ ] File system paths and permissions
[ ] Network access (DNS, firewalls, proxies)
[ ] OS-level differences (glibc version, timezone, locale)
[ ] Config files (which one is actually loaded?)
```

## 5. Third-Party Dependency Changes

**Symptoms:** Code broke without any changes to your codebase.

**Strategy:** Check what changed externally — versions, APIs, rate limits, certificates.

**Example (Node.js):**
```javascript
// Bug: Tests started failing Monday, no code changes since Friday
// Symptom: "TypeError: response.data.items is not iterable"

// Step 1: What changed?
// git log --since="Friday" → nothing
// npm audit → nothing
// Check CI logs: package-lock.json changed!

// Step 2: Find the dependency change
// npm ls axios → axios@1.7.0 (was 1.6.8 on Friday)
// Read changelog: "Breaking: Empty responses return null instead of {items:[]}"

// Step 3: Verify
// Pin: "axios": "1.6.8" in package.json → tests pass
// Confirmed: axios 1.7.0 changed empty response format

// Root cause: Unpinned dependency with breaking change
// Fix: Handle null response + pin dependency version
```

**Investigation steps:**
1. `git log` — Confirm no code changes
2. Check dependency lock files for version bumps
3. Check third-party status pages / changelogs
4. Check certificate expirations (`openssl s_client`)
5. Check API deprecation notices
6. Compare against pinned/locked versions

## 6. Build / Compilation Errors

**Symptoms:** Code doesn't compile or build step fails.

**Strategy:** Read the error message literally. Build errors are usually the most honest.

**This is the one bug type where Phase 1 Step 1 is often sufficient.** Read the error, fix the error. If the error is unclear, check:
- Dependency version compatibility
- Generated code that's out of date (`go generate`, protobuf, etc.)
- Cache staleness (`go clean -cache`, `rm -rf node_modules`, `mvn clean`)

## Decision Flowchart

```
Bug Symptoms
    |
    +--> Wrong output, no errors? ---------> Logic Error (Strategy 1)
    |
    +--> Intermittent / flaky? ------------> Race Condition (Strategy 2)
    |
    +--> Gradual degradation? -------------> Memory/Perf (Strategy 3)
    |
    +--> Works here, fails there? ---------> Environment (Strategy 4)
    |
    +--> Broke without code changes? ------> Dependency (Strategy 5)
    |
    +--> Won't compile / build fails? -----> Build Error (Strategy 6)
    |
    +--> Multiple symptoms? ---------------> Start with most specific,
                                             then check for shared root cause
```

## Cross-Cutting Principle

Regardless of bug type, the systematic debugging process still applies:
1. **Triage severity** (P0/P1/P2)
2. **Classify bug type** (use this document)
3. **Apply type-specific investigation** (Phase 1)
4. **Continue with Phases 2-4** as normal

The bug type determines HOW you investigate in Phase 1. It doesn't change WHEN you investigate (always before fixing).
