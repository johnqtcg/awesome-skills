# Concurrency Testing — Deterministic Control Techniques

> Referenced from [SKILL.md](../SKILL.md). Covers reliable synchronization, race detection, panic recovery, and `t.Parallel()` safety.

## Channel Barrier Synchronization

Replace `time.Sleep` with channel-based barriers for deterministic test control.

### Pattern: Gate all goroutines to start simultaneously

```go
func TestConcurrent_ChannelBarrier(t *testing.T) {
	gate := make(chan struct{})
	var mu sync.Mutex
	var results []string

	for i := 0; i < 5; i++ {
		go func(id int) {
			<-gate // all goroutines block here until gate closes
			mu.Lock()
			results = append(results, fmt.Sprintf("worker-%d", id))
			mu.Unlock()
		}(i)
	}

	close(gate) // release all at once — maximizes contention
	// Use WaitGroup or other mechanism to wait for completion
}
```

### Pattern: Step-by-step orchestration with buffered channels

```go
func TestSequencedOperations(t *testing.T) {
	step1Done := make(chan struct{}, 1)
	step2Done := make(chan struct{}, 1)

	svc := NewPipeline(fakeDeps)

	go func() {
		svc.Stage1(ctx)
		step1Done <- struct{}{}
	}()

	<-step1Done // wait for stage 1 to complete

	go func() {
		svc.Stage2(ctx)
		step2Done <- struct{}{}
	}()

	<-step2Done
	// Now assert final state
	assert.Equal(t, "complete", svc.Status())
}
```

---

## `-race` Detection in Practice

### How to run

```bash
# Single test
go test -run TestConcurrent -v -race ./pkg/...

# Full package
go test -race ./pkg/...

# With coverage
go test -race -coverprofile=coverage.out -covermode=atomic ./pkg/...
```

### How to trigger a race

Design tests that exercise shared state from multiple goroutines concurrently:

```go
func TestCounter_RaceDetection(t *testing.T) {
	counter := NewCounter() // not goroutine-safe? -race will catch it

	var wg sync.WaitGroup
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			counter.Increment()
		}()
	}
	wg.Wait()

	assert.Equal(t, 100, counter.Value())
}
```

### Reading race detector output

```
WARNING: DATA RACE
Write at 0x00c0000b4010 by goroutine 8:
  pkg.(*Counter).Increment()
      /path/counter.go:15 +0x3a

Previous read at 0x00c0000b4010 by goroutine 7:
  pkg.(*Counter).Value()
      /path/counter.go:19 +0x2e
```

Key fields:
- **Write at / Read at**: the conflicting memory accesses
- **by goroutine N**: which goroutines are involved
- **file:line**: exact source location of each access

Fix: add `sync.Mutex`, use `sync/atomic`, or redesign to avoid shared mutable state.

---

## Panic Recovery Testing

When target code has `defer func() { if r := recover(); r != nil { ... } }()`, test that:
1. The panic is recovered (test does not crash)
2. A proper error is returned
3. No partial state is leaked

```go
func TestSafeExecute_PanicRecovery(t *testing.T) {
	tests := []struct {
		name      string
		action    func() error
		wantErr   string
	}{
		{
			name: "nil pointer panic is recovered",
			action: func() error {
				var p *int
				_ = *p // panic: nil pointer dereference
				return nil
			},
			wantErr: "panic recovered",
		},
		{
			name: "string panic is recovered",
			action: func() error {
				panic("something went wrong")
			},
			wantErr: "something went wrong",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := SafeExecute(tt.action)
			require.Error(t, err)
			assert.Contains(t, err.Error(), tt.wantErr)
		})
	}
}
```

---

## Error Fan-In Verification

When using `errgroup` or manual goroutine error collection, verify that any single failure fails the whole operation.

```go
func TestProcessAll_ErrorFanIn(t *testing.T) {
	tests := []struct {
		name     string
		errors   map[string]error
		wantErr  bool
		wantMsg  string
	}{
		{
			name:    "all succeed",
			errors:  map[string]error{"a": nil, "b": nil, "c": nil},
			wantErr: false,
		},
		{
			name:    "middle task fails",
			errors:  map[string]error{"a": nil, "b": errors.New("b-failed"), "c": nil},
			wantErr: true,
			wantMsg: "b-failed",
		},
		{
			name:    "first task fails",
			errors:  map[string]error{"a": errors.New("a-failed"), "b": nil, "c": nil},
			wantErr: true,
			wantMsg: "a-failed",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			fake := &fakeProcessor{errors: tt.errors}
			svc := NewBatchProcessor(fake)

			err := svc.ProcessAll(ctx, []string{"a", "b", "c"})

			if tt.wantErr {
				require.Error(t, err)
				assert.Contains(t, err.Error(), tt.wantMsg)
			} else {
				require.NoError(t, err)
			}
		})
	}
}
```

---

## `t.Parallel()` Safety Rules

### When to use `t.Parallel()`

- Subtests are fully independent (no shared mutable state)
- Each subtest uses its own fake/stub instances
- No shared temp directories, files, or process-wide resources
- Test does not modify global variables or environment

### When NOT to use `t.Parallel()`

- Subtests share a mutable fake (e.g., same `fakeRepo` instance with recorded calls)
- Tests use `t.Setenv` (not safe with `t.Parallel()` in Go < 1.24)
- Tests modify package-level variables
- Tests use shared temp directories without isolation
- Tests depend on execution order (they shouldn't, but if they do, fix the design first)

### Safe pattern

```go
func TestUserService(t *testing.T) {
	tests := []struct {
		name string
		// ... fields
	}{
		// ... cases
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel() // safe: each iteration gets its own tt copy

			// Create fresh fake per subtest
			fake := &fakeRepo{user: tt.inputUser}
			svc := NewUserService(fake)

			got, err := svc.GetUser(ctx, tt.inputID)
			// ... assertions
		})
	}
}
```

---

## Deterministic Ordering with Channel Sequencing

When you need to verify behavior that depends on completion order, use channel handoffs — never `time.Sleep`:

```go
func TestOrderedCompletion(t *testing.T) {
	var order []string
	var mu sync.Mutex

	var wg sync.WaitGroup
	wg.Add(3)

	step1 := make(chan struct{})
	step2 := make(chan struct{})
	step3 := make(chan struct{})
	done1 := make(chan struct{})
	done2 := make(chan struct{})

	go func() {
		defer wg.Done()
		<-step1
		mu.Lock()
		order = append(order, "first")
		mu.Unlock()
		close(done1)
	}()

	go func() {
		defer wg.Done()
		<-step2
		mu.Lock()
		order = append(order, "second")
		mu.Unlock()
		close(done2)
	}()

	go func() {
		defer wg.Done()
		<-step3
		mu.Lock()
		order = append(order, "third")
		mu.Unlock()
	}()

	// Sequenced release: each stage waits for the previous to complete
	close(step1)
	<-done1
	close(step2)
	<-done2
	close(step3)

	wg.Wait()
	assert.Equal(t, []string{"first", "second", "third"}, order)
}
```

Key principle: use `close(done)` + `<-done` handoffs to enforce ordering deterministically. Never use `time.Sleep` for synchronization — it introduces flakiness and race conditions.