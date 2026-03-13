# API 3-Layer TDD Template

Use this sequence for API-related changes:

1. Service tests first (business contract) → Red
2. Handler tests second (HTTP contract) → Red
3. Repo tests only when data logic changed

## Scenario Matrix

### Handler (HTTP contract)

| Scenario | Status | Assert |
|----------|--------|--------|
| success | 200 | body fields, headers |
| bad_request | 400 | validation error message |
| unauthorized | 401 | auth failure |
| forbidden | 403 | permission denied |
| not_found | 404 | id mismatch / resource missing |
| rate_limit | 429 | retry-after or error message |
| service_error | 500 | generic error, no sensitive leak |
| timeout | 504 or 408 | timeout semantics |
| validation_error | 400 | field-level validation details |

### Service (business contract)

| Scenario | Assert |
|----------|--------|
| success | output fields, invariants |
| dependency_error | error propagated, no partial payload |
| boundary_empty | empty input/output behavior |
| context_canceled | early return, ctx respected |
| not_found | explicit not-found semantics |

### Repo (data contract)

| Scenario | Assert |
|----------|--------|
| success | rows mapped correctly |
| empty_result | nil/empty, no error |
| db_error | error surfaced |
| duplicate_key | conflict handling if applicable |

## Naming Pattern

- `TestXxxHandler/Method/case`
- `TestXxxService/Method/case`
- `TestXxxRepo/Method/case`

## Complete Handler Test Example

```go
func TestUserHandler_Create(t *testing.T) {
	tests := []struct {
		name       string
		body       string
		setupSvc   func(*fakeUserService)
		wantStatus int
		wantBody   string
	}{
		{
			name: "success",
			body: `{"name":"alice","email":"alice@example.com"}`,
			setupSvc: func(s *fakeUserService) {
				s.createFn = func(ctx context.Context, u User) (*User, error) {
					return &User{ID: "u-1", Name: u.Name, Email: u.Email}, nil
				}
			},
			wantStatus: http.StatusOK,
			wantBody:   `"id":"u-1"`,
		},
		{
			name:       "bad_request: empty body",
			body:       `{}`,
			wantStatus: http.StatusBadRequest,
			wantBody:   `"error"`,
		},
		{
			name: "service_error: dependency failure",
			body: `{"name":"alice","email":"alice@example.com"}`,
			setupSvc: func(s *fakeUserService) {
				s.createFn = func(ctx context.Context, u User) (*User, error) {
					return nil, errors.New("db: connection refused")
				}
			},
			wantStatus: http.StatusInternalServerError,
			wantBody:   `"error"`, // no sensitive info leaked
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			svc := &fakeUserService{}
			if tt.setupSvc != nil {
				tt.setupSvc(svc)
			}
			handler := NewUserHandler(svc)
			req := httptest.NewRequest(http.MethodPost, "/users", strings.NewReader(tt.body))
			req.Header.Set("Content-Type", "application/json")
			rec := httptest.NewRecorder()

			handler.Create(rec, req)

			assert.Equal(t, tt.wantStatus, rec.Code)
			assert.Contains(t, rec.Body.String(), tt.wantBody)
		})
	}
}
```

## Complete Service Test Example

```go
func TestUserService_Create(t *testing.T) {
	t.Run("success", func(t *testing.T) {
		repo := &fakeUserRepo{
			saveFn: func(ctx context.Context, u *User) error {
				u.ID = "u-1"
				return nil
			},
		}
		svc := NewUserService(repo)
		user, err := svc.Create(ctx, User{Name: "alice", Email: "alice@example.com"})
		require.NoError(t, err)
		assert.Equal(t, "u-1", user.ID)
		assert.Equal(t, "alice", user.Name)
	})
	t.Run("dependency_error: repo failure", func(t *testing.T) {
		repo := &fakeUserRepo{
			saveFn: func(ctx context.Context, u *User) error {
				return errors.New("db: timeout")
			},
		}
		svc := NewUserService(repo)
		_, err := svc.Create(ctx, User{Name: "alice", Email: "alice@example.com"})
		require.Error(t, err)
		assert.Contains(t, err.Error(), "timeout")
	})
	t.Run("killer: empty name rejected", func(t *testing.T) {
		svc := NewUserService(&fakeUserRepo{})
		_, err := svc.Create(ctx, User{Name: "", Email: "a@b.com"})
		require.Error(t, err)
		assert.Contains(t, err.Error(), "name")
	})
}
```

## Layer Test Ordering for TDD

```
Outside-In (new endpoint):
  1. Handler test (Red) → stub service
  2. Service test (Red) → stub repo
  3. Repo test (Red) → if data mapping logic exists
  4. Green: implement repo → service → handler
  5. All tests pass

Inside-Out (new business rule):
  1. Service test (Red) → stub repo
  2. Green: implement service
  3. Handler test (Red) → verify HTTP contract
  4. Green: wire handler
```
