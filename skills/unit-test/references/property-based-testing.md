# Property-Based Testing Patterns for Go

Reference material for the `unit-test` skill. Load when target code matches property-based testing trigger patterns.

## When to Use Property-Based Testing

Use when the target function exhibits **invariants** that should hold across a wide input space, not just at hand-picked boundaries.

### Trigger Patterns

| Pattern | Invariant | Best For |
|---------|-----------|----------|
| Roundtrip | `decode(encode(x)) == x` | Serializers, encoders, marshalers |
| Idempotency | `f(f(x)) == f(x)` | Normalizers, formatters, canonicalizers |
| Preservation | `len(output) == len(input)` | Transforms that must not drop/duplicate |
| Commutativity | `f(a,b) == f(b,a)` | Set operations, merge functions |
| Parse validity | valid input → no panic, valid output | Parsers, validators |
| Monotonicity | `a ≤ b → f(a) ≤ f(b)` | Scoring, ranking, pricing functions |

### When NOT to Use

- **Trivial functions** with no meaningful invariant (e.g., `Add(a, b int) int` — the invariant is just the implementation itself)
- **Functions where all interesting behavior is at boundaries** — table-driven tests are more precise
- **Functions with complex preconditions** that make random valid input generation impractical
- **Side-effecting functions** that are hard to observe through return values alone

## Approach 1: `testing/quick` (Simplest)

Best for functions with simple input types (`string`, `int`, `[]byte`, `float64`).

### Roundtrip Pattern

```go
import "testing/quick"

func TestEncodeDecodeRoundtrip(t *testing.T) {
    f := func(input string) bool {
        encoded := Encode(input)
        decoded, err := Decode(encoded)
        return err == nil && decoded == input
    }
    if err := quick.Check(f, nil); err != nil {
        t.Error(err)
    }
}
```

### Idempotency Pattern

```go
func TestNormalizeIdempotent(t *testing.T) {
    f := func(input string) bool {
        once := Normalize(input)
        twice := Normalize(once)
        return once == twice
    }
    if err := quick.Check(f, nil); err != nil {
        t.Error(err)
    }
}
```

### Preservation Pattern

```go
func TestTransformPreservesLength(t *testing.T) {
    f := func(items []int) bool {
        if len(items) == 0 {
            return true // skip empty — tested in table-driven
        }
        result := Transform(items)
        return len(result) == len(items)
    }
    if err := quick.Check(f, nil); err != nil {
        t.Error(err)
    }
}
```

### Controlling Iterations

```go
// Default: 100 iterations. Override with config:
config := &quick.Config{MaxCount: 500}
if err := quick.Check(f, config); err != nil {
    t.Error(err)
}
```

## Approach 2: Hand-Rolled Generators (Complex Domain Types)

When `testing/quick` cannot generate valid domain objects, use hand-rolled generators with **deterministic seeds** for reproducibility.

```go
func TestTransformPreservesIdentities(t *testing.T) {
    rng := rand.New(rand.NewSource(42)) // deterministic seed for reproducibility
    for i := 0; i < 100; i++ {
        input := generateRandomOrders(rng, 1+rng.Intn(50))
        output := TransformOrders(input)

        // Preservation: no items dropped or duplicated
        if len(output) != len(input) {
            t.Errorf("iteration %d: len(output)=%d, want %d", i, len(output), len(input))
        }

        // Identity preservation: same IDs in output
        inputIDs := extractIDs(input)
        outputIDs := extractIDs(output)
        if !reflect.DeepEqual(inputIDs, outputIDs) {
            t.Errorf("iteration %d: IDs mismatch", i)
        }
    }
}

func generateRandomOrders(rng *rand.Rand, n int) []Order {
    orders := make([]Order, n)
    for i := range orders {
        orders[i] = Order{
            ID:     fmt.Sprintf("order-%d", i),
            Amount: rng.Float64() * 1000,
            Status: []string{"pending", "active", "done"}[rng.Intn(3)],
        }
    }
    return orders
}
```

**Key principles:**
- Use a fixed seed (`rand.NewSource(42)`) so failures are reproducible
- Generate at least 100 iterations for confidence
- Assert invariants, not exact values — exact values belong in table-driven tests
- Skip degenerate inputs that are better handled by explicit boundary cases

## Relationship to Table-Driven Tests

Property-based and table-driven tests are **complementary**, not alternatives:

| Aspect | Table-Driven | Property-Based |
|--------|-------------|----------------|
| Input selection | Hand-picked boundaries | Randomized across space |
| Assertion style | Exact expected values | Invariant holds (boolean) |
| Strength | Precise boundary coverage | Finds unexpected edge cases |
| Weakness | Limited to human imagination | Cannot verify exact outputs |

**Best practice**: Write table-driven tests for specific boundary cases, then add property-based tests for broad invariant verification.

## Interaction with Killer Cases (Standard + Strict)

In Standard and Strict modes, property-based tests do **not** replace killer cases. A killer case targets a specific named defect with fault injection; a property-based test verifies a general invariant. They serve different purposes:

- **Killer case**: "If the loop uses `i < len-1`, the last element is dropped" → specific defect hypothesis
- **Property-based test**: "For all valid inputs, `len(output) == len(input)`" → general invariant

When both apply, include both. The killer case catches the specific known risk; the property-based test catches unknown risks in the same invariant space.