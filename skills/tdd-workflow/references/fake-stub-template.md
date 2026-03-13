# Fake Stub Template Guidance

## Design Rules

- Keep fakes minimal: only methods used by current test scope.
- Use function fields (`xxxFn`) for per-case behavior override.
- Track `calls` and `lastArgs` for interaction assertions.
- Instantiate new fakes per subtest; avoid shared mutable state.
- Support error injection via `xxxFn` returning error.

## Minimal Skeleton

```go
type fakeRepo struct {
    findFn    func(ctx context.Context, id int64) (Entity, error)
    findCalls int
    lastID    int64
}

func (f *fakeRepo) Find(ctx context.Context, id int64) (Entity, error) {
    f.findCalls++
    f.lastID = id
    if f.findFn != nil {
        return f.findFn(ctx, id)
    }
    return Entity{}, nil
}
```

## Error Injection Example

```go
// dependency_error scenario
t.Run("dependency_error", func(t *testing.T) {
    f := &fakeRepo{
        findFn: func(ctx context.Context, id int64) (Entity, error) {
            return Entity{}, errors.New("db: connection refused")
        },
    }
    svc := NewUserService(f)
    _, err := svc.GetUser(ctx, 1)
    require.Error(t, err)
    assert.Contains(t, err.Error(), "connection refused")
})
```

## Assertion Style (Adapt to Project)

```go
// testify
require.NoError(t, err)
assert.Equal(t, "u-1", user.ID)

// stdlib
if err != nil {
    t.Fatalf("GetUser() error = %v, want nil", err)
}
if user.ID != "u-1" {
    t.Errorf("ID = %q, want %q", user.ID, "u-1")
}

// go-cmp
if diff := cmp.Diff(want, got); diff != "" {
    t.Errorf("mismatch (-want +got):\n%s", diff)
}
```
