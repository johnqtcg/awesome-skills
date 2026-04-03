# Go Database Patterns

Deep-dive reference for database review patterns in SKILL.md step 6.

---

## sql.Rows Close

```go
// BAD: rows never closed — connection leaks back to pool only on GC
rows, _ := db.Query("SELECT id, name FROM users")
for rows.Next() {
    var id int
    var name string
    rows.Scan(&id, &name)
    fmt.Println(id, name)
}

// GOOD: defer Close immediately after error check
rows, err := db.QueryContext(ctx, "SELECT id, name FROM users")
if err != nil {
    return fmt.Errorf("query users: %w", err)
}
defer rows.Close()

for rows.Next() {
    var id int
    var name string
    if err := rows.Scan(&id, &name); err != nil {
        return fmt.Errorf("scan user row: %w", err)
    }
    fmt.Println(id, name)
}
if err := rows.Err(); err != nil {
    return fmt.Errorf("iterate users: %w", err)
}
```

Subtle case — early break still needs Close:

```go
rows, err := db.QueryContext(ctx, "SELECT id, name FROM users")
if err != nil {
    return fmt.Errorf("query users: %w", err)
}
defer rows.Close() // critical: called even if loop breaks early

for rows.Next() {
    var id int
    var name string
    if err := rows.Scan(&id, &name); err != nil {
        return fmt.Errorf("scan row: %w", err)
    }
    if id == targetID {
        result = name
        break // rows.Close() runs via defer — releases the connection
    }
}
if err := rows.Err(); err != nil {
    return fmt.Errorf("iterate users: %w", err)
}
```

Key points:
- Without `defer rows.Close()`, the underlying connection is held until the garbage collector finalizes the object
- `rows.Close()` is idempotent — safe to call multiple times
- Always check `rows.Err()` after the loop to catch iteration errors (network timeout, cancelled context)

---

## Transaction Rollback Pattern

```go
// BAD: manual commit/rollback with missed error paths
tx, err := db.BeginTx(ctx, nil)
if err != nil {
    return err
}
_, err = tx.ExecContext(ctx, "INSERT INTO orders (user_id, total) VALUES ($1, $2)", userID, total)
if err != nil {
    tx.Rollback()
    return err
}
_, err = tx.ExecContext(ctx, "UPDATE inventory SET qty = qty - $1 WHERE item_id = $2", qty, itemID)
if err != nil {
    // BUG: if this Rollback fails or is forgotten, connection leaks
    tx.Rollback()
    return err
}
return tx.Commit() // if Commit fails, no rollback attempted

// GOOD: defer Rollback + Commit overrides
tx, err := db.BeginTx(ctx, nil)
if err != nil {
    return fmt.Errorf("begin tx: %w", err)
}
defer tx.Rollback() // no-op after successful Commit

if _, err := tx.ExecContext(ctx, "INSERT INTO orders (user_id, total) VALUES ($1, $2)", userID, total); err != nil {
    return fmt.Errorf("insert order: %w", err)
}
if _, err := tx.ExecContext(ctx, "UPDATE inventory SET qty = qty - $1 WHERE item_id = $2", qty, itemID); err != nil {
    return fmt.Errorf("update inventory: %w", err)
}
return tx.Commit()
```

Why this works:
- `tx.Rollback()` after a successful `tx.Commit()` returns `sql.ErrTxDone` and is effectively a no-op
- Every error return path triggers the deferred Rollback automatically — no path can leak a transaction
- The pattern scales safely when adding more statements; no need to add Rollback calls per error

---

## Connection Pool Configuration

```go
// BAD: using defaults — unlimited open connections
db, err := sql.Open("postgres", dsn)
if err != nil {
    log.Fatal(err)
}
// pool defaults: MaxOpenConns=0 (unlimited), MaxIdleConns=2
// under load this exhausts database connection limits

// GOOD: configure pool for production
db, err := sql.Open("postgres", dsn)
if err != nil {
    log.Fatal(err)
}
db.SetMaxOpenConns(25)              // match DB max_connections / num_instances
db.SetMaxIdleConns(10)              // keep warm connections ready; ≤ MaxOpenConns
db.SetConnMaxLifetime(5 * time.Minute)  // recycle before DB-side idle timeout
db.SetConnMaxIdleTime(1 * time.Minute)  // close idle connections faster under low load
```

Guidelines:
- `MaxOpenConns`: total open connections (active + idle). Set to `DB max_connections / number_of_app_instances` with headroom for admin connections
- `MaxIdleConns`: warm connections kept ready. Too low → frequent reconnection overhead; too high → wasted DB memory
- `ConnMaxLifetime`: forces reconnection to pick up DNS changes, rebalance across replicas, and avoid server-side idle timeouts (typically < DB `wait_timeout`)
- `ConnMaxIdleTime` (Go 1.15+): closes connections idle longer than this; useful for bursty workloads to shrink the pool during quiet periods
- Always monitor `db.Stats()` in production (expose via metrics endpoint)

---

## Context Propagation

```go
// BAD: no context — query cannot be cancelled or timed out
rows, err := db.Query("SELECT * FROM large_table WHERE status = $1", status)

// GOOD: propagate request context — cancellation and deadlines apply
rows, err := db.QueryContext(ctx, "SELECT * FROM large_table WHERE status = $1", status)
```

All context-aware variants:

```go
db.QueryContext(ctx, query, args...)
db.QueryRowContext(ctx, query, args...)
db.ExecContext(ctx, query, args...)
db.PrepareContext(ctx, query)
db.BeginTx(ctx, opts)
tx.ExecContext(ctx, query, args...)
tx.QueryContext(ctx, query, args...)
tx.QueryRowContext(ctx, query, args...)
```

Benefits:
- HTTP handler cancellation (client disconnect) terminates long-running queries
- Timeout propagation prevents a single slow query from holding a connection indefinitely
- Tracing middleware can inject span context for observability
- The non-context variants (`db.Query`, `db.Exec`) are effectively `context.Background()` — they never cancel

---

## N+1 Query Detection

```go
// BAD: N+1 — one query per order to fetch items (flagged in review)
orders, err := getOrders(ctx, db, userID)
if err != nil {
    return err
}
for i := range orders {
    items, err := db.QueryContext(ctx,
        "SELECT id, name, price FROM items WHERE order_id = $1", orders[i].ID)
    if err != nil {
        return fmt.Errorf("query items for order %d: %w", orders[i].ID, err)
    }
    defer items.Close() // BUG: deferred in loop — closes only when function returns
    for items.Next() {
        var item Item
        if err := items.Scan(&item.ID, &item.Name, &item.Price); err != nil {
            return err
        }
        orders[i].Items = append(orders[i].Items, item)
    }
}

// GOOD: batch query with WHERE IN
orderIDs := make([]interface{}, len(orders))
for i, o := range orders {
    orderIDs[i] = o.ID
}
query, args := buildInQuery("SELECT id, order_id, name, price FROM items WHERE order_id IN", orderIDs)
rows, err := db.QueryContext(ctx, query, args...)
if err != nil {
    return fmt.Errorf("batch query items: %w", err)
}
defer rows.Close()

itemsByOrder := make(map[int64][]Item)
for rows.Next() {
    var item Item
    var orderID int64
    if err := rows.Scan(&item.ID, &orderID, &item.Name, &item.Price); err != nil {
        return fmt.Errorf("scan item: %w", err)
    }
    itemsByOrder[orderID] = append(itemsByOrder[orderID], item)
}
if err := rows.Err(); err != nil {
    return fmt.Errorf("iterate items: %w", err)
}
for i := range orders {
    orders[i].Items = itemsByOrder[orders[i].ID]
}
```

Telltale patterns to flag in review:
- `db.Query` / `db.QueryContext` inside a `for` loop
- `defer rows.Close()` inside a loop (defers pile up, connections held until function exit)
- Number of queries scales with data size rather than being constant

Alternative approaches: JOIN query, CTE, or ORM eager-loading (e.g., GORM `Preload`).

---

## Prepared Statement Lifecycle

```go
// BAD: Prepare inside a loop — creates and closes a statement per iteration
for _, u := range users {
    stmt, err := db.PrepareContext(ctx, "INSERT INTO audit_log (user_id, action) VALUES ($1, $2)")
    if err != nil {
        return err
    }
    _, err = stmt.ExecContext(ctx, u.ID, action)
    stmt.Close()
    if err != nil {
        return err
    }
}

// GOOD: prepare once, execute many times
stmt, err := db.PrepareContext(ctx, "INSERT INTO audit_log (user_id, action) VALUES ($1, $2)")
if err != nil {
    return fmt.Errorf("prepare audit insert: %w", err)
}
defer stmt.Close()

for _, u := range users {
    if _, err := stmt.ExecContext(ctx, u.ID, action); err != nil {
        return fmt.Errorf("audit log user %d: %w", u.ID, err)
    }
}
```

Notes:
- `database/sql` prepared statements are connection-agnostic: the driver re-prepares transparently if the connection changes
- Some drivers (e.g., `lib/pq`, `pgx`) auto-prepare repeated queries internally — explicit `Prepare` may be unnecessary for simple cases
- For bulk inserts consider `COPY` (Postgres) or batch `INSERT ... VALUES (...), (...)` instead of per-row Exec
- Prepared statements hold server-side resources; always `defer stmt.Close()` to release them

---

## Null Handling

```go
// BAD: scanning nullable column into non-nullable type — panics or zero-value silently
var name string
var age int
err := db.QueryRowContext(ctx, "SELECT name, age FROM users WHERE id = $1", id).Scan(&name, &age)
// if age is NULL in the DB: Scan returns error "converting NULL to int is unsupported"

// GOOD: use sql.Null* types for nullable columns
var name sql.NullString
var age sql.NullInt64
err := db.QueryRowContext(ctx, "SELECT name, age FROM users WHERE id = $1", id).Scan(&name, &age)
if err != nil {
    return fmt.Errorf("query user %d: %w", id, err)
}
if name.Valid {
    user.Name = name.String
}
if age.Valid {
    user.Age = int(age.Int64)
}
```

Alternative — pointer types:

```go
var name *string
var age *int64
err := db.QueryRowContext(ctx, "SELECT name, age FROM users WHERE id = $1", id).Scan(&name, &age)
if err != nil {
    return fmt.Errorf("query user %d: %w", id, err)
}
// name and age are nil when DB value is NULL
```

When to use which:
- `sql.Null*`: explicit Valid field, no nil-pointer risk, marshals to JSON as `{"String":"...","Valid":true}` by default (needs custom marshaler for clean JSON)
- `*T` pointers: cleaner JSON marshaling (`null` or value), but requires nil checks at every usage site
- For new code with JSON APIs, pointer types are often more practical

---

## sql.ErrNoRows Handling

```go
// BAD: treating "not found" as a server error — returns 500 to clients
var user User
err := db.QueryRowContext(ctx, "SELECT id, name FROM users WHERE id = $1", id).Scan(&user.ID, &user.Name)
if err != nil {
    return fmt.Errorf("query user: %w", err) // wraps ErrNoRows as internal error
}

// GOOD: distinguish "not found" from actual errors
var user User
err := db.QueryRowContext(ctx, "SELECT id, name FROM users WHERE id = $1", id).Scan(&user.ID, &user.Name)
if errors.Is(err, sql.ErrNoRows) {
    return nil, ErrUserNotFound // business-level "not found"
}
if err != nil {
    return nil, fmt.Errorf("query user %d: %w", id, err)
}
return &user, nil
```

Key points:
- `QueryRow.Scan` returns `sql.ErrNoRows` when zero rows match — this is normal for lookups by ID, email, etc.
- Use `errors.Is` (not `==`) because the error might be wrapped
- Map to a domain-specific sentinel (e.g., `ErrUserNotFound`) so HTTP handlers can return 404 instead of 500
- `db.Query` (multi-row) does **not** return `ErrNoRows` — an empty result set is not an error; only `QueryRow` has this behavior

---

## Count-First Guard (Skip Find When Total Is Zero)

When a function performs both a `Count` and a `Find` query, consider executing `Count` first and returning early if the result is zero. This eliminates the more expensive `Find` query for the common case of empty result sets.

```go
// BAD: always executes both Count and Find regardless of data
func ListLayout(ctx context.Context, uid, corpID int64, page, pageSize int) ([]*Layout, int64, error) {
    var total int64
    var list []*Layout

    if err := db.WithContext(ctx).Model(&Layout{}).
        Where("uid = ? AND corp_id = ?", uid, corpID).
        Count(&total).Error; err != nil {
        return nil, 0, fmt.Errorf("ListLayout count: %w", err)
    }
    if err := db.WithContext(ctx).Model(&Layout{}).
        Where("uid = ? AND corp_id = ?", uid, corpID).
        Order("updated_at desc").Limit(pageSize).Offset((page-1)*pageSize).
        Find(&list).Error; err != nil {
        return nil, 0, fmt.Errorf("ListLayout find: %w", err)
    }
    return list, total, nil
}

// GOOD: count-first guard skips Find when total is 0
func ListLayout(ctx context.Context, uid, corpID int64, page, pageSize int) ([]*Layout, int64, error) {
    var total int64

    if err := db.WithContext(ctx).Model(&Layout{}).
        Where("uid = ? AND corp_id = ?", uid, corpID).
        Count(&total).Error; err != nil {
        return nil, 0, fmt.Errorf("ListLayout count: %w", err)
    }
    if total == 0 {
        return []*Layout{}, 0, nil // skip Find entirely
    }

    list := make([]*Layout, 0, pageSize)
    if err := db.WithContext(ctx).Model(&Layout{}).
        Where("uid = ? AND corp_id = ?", uid, corpID).
        Order("updated_at desc").Limit(pageSize).Offset((page-1)*pageSize).
        Find(&list).Error; err != nil {
        return nil, 0, fmt.Errorf("ListLayout find: %w", err)
    }
    return list, total, nil
}
```

When this optimization is worth applying:
- **High-frequency endpoint**: the function is called often (e.g., a page that every user visits).
- **Common empty case**: a significant fraction of users/entities have zero records for this query (e.g., most users have never created a Layout).
- **Cost asymmetry**: `Count` is a lightweight aggregate; `Find` scans and transfers rows.

When NOT to apply:
- The empty-result rate is very low (< 5%) — the extra `Count` round-trip adds latency without saving the `Find`.
- The `Count` and `Find` share the same transaction boundary and consistency is required — use a transaction wrapping both, not a guard pattern.

Key points:
- Return an empty non-nil slice (`[]*T{}` or `make([]*T, 0)`) rather than `nil` when skipping `Find`, so JSON marshaling produces `[]` instead of `null`.
- Pre-allocate the result slice with `make([]*Layout, 0, pageSize)` to avoid repeated reallocations during ORM scan.
- The guard only works if `Count` runs first; reversing the order defeats the optimization.

---

## See Also

- [go-error-and-quality.md](go-error-and-quality.md) — error wrapping, sentinel errors, and `errors.Is`/`errors.As` patterns
- [go-performance-patterns.md](go-performance-patterns.md) — connection pooling performance, slice pre-allocation for batch results
- [go-security-patterns.md](go-security-patterns.md) — SQL injection prevention with parameterized queries
