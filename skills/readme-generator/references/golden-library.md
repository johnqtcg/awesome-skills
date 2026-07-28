# Golden Example: Go Library (Template B)

**Repo signals**: `go.mod` (Go 1.21) · exported `pkg/` with `validator.go`, `error.go`, `rules.go` ·
`validator_test.go` containing `Benchmark*` functions · no `cmd/` · no Makefile · no coverage
config · `LICENSE` (Apache-2.0) · `.github/workflows/test.yml`.

Note what is absent: benchmark *functions* exist, benchmark *results* do not, and there is no
coverage config. So the README shows how to run both and reports neither.

````markdown
![CI](https://github.com/acme/govalidate/actions/workflows/test.yml/badge.svg)
![Go](https://img.shields.io/badge/Go-1.21+-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-blue)

# govalidate

Struct validation library for Go with composable rules and zero reflection at runtime.

## Installation

```bash
go get github.com/acme/govalidate@latest
```

## Quick Usage

```go
package main

import "github.com/acme/govalidate"

type User struct {
    Name  string `validate:"required,min=2,max=50"`
    Email string `validate:"required,email"`
    Age   int    `validate:"min=0,max=150"`
}

func main() {
    v := govalidate.New()
    user := User{Name: "A", Email: "bad", Age: -1}
    errs := v.Validate(user)
    // errs: [Name: min=2, Email: invalid format, Age: min=0]
}
```

## API Overview

| Function/Type | Description |
|--------------|-------------|
| `New()` | Create a new validator instance |
| `Validate(v any) []Error` | Validate struct, return all errors |
| `RegisterRule(name, fn)` | Add custom validation rule |
| `Error` | Validation error with Field, Rule, Message |

Full API reference: [pkg.go.dev/github.com/acme/govalidate](https://pkg.go.dev/github.com/acme/govalidate)

## Built-in Rules

| Rule | Example Tag | Description |
|------|------------|-------------|
| `required` | `validate:"required"` | Field must be non-zero |
| `min` / `max` | `validate:"min=2,max=50"` | Length or value bounds |
| `email` | `validate:"email"` | RFC 5322 email format |
| `url` | `validate:"url"` | Valid URL |
| `oneof` | `validate:"oneof=a b c"` | Value must be one of listed |

## Compatibility

- Go >= 1.21
- No CGO dependencies
- Works with `reflect` only during rule compilation (zero reflection at validation time)

## Benchmarks

`validator_test.go` defines `BenchmarkValidateSmallStruct` and
`BenchmarkValidateLargeStruct`. Run them locally:

```bash
go test -bench=. -benchmem ./...
```

## Testing

```bash
go test ./...                # all tests
go test -race ./...          # race detection
go test -cover ./...         # coverage report
```

## License

Apache-2.0 — see [LICENSE](LICENSE).

## Documentation Maintenance

Update this README when:
- the exported API surface changes
- a built-in rule is added or removed
- the minimum Go version in `go.mod` changes
````

**Why no benchmark numbers**: a benchmark result is a property of the machine that produced
it. It belongs in a README only when the repo commits that output — a `benchstat` artifact
under `testdata/`, or a published CI job — so a reader can trace it back. This repo has the
benchmark *functions* and none of that output, so the README shows how to run them and
reports nothing. Same rule for the coverage command.

**Evidence mapping (assistant response)**:

| README Section | Evidence File(s) | Reason |
|---|---|---|
| Badges | `.github/workflows/test.yml`, `go.mod`, `LICENSE` | CI, Go 1.21, Apache-2.0 |
| Installation | `go.mod` module path | Standard `go get` |
| Quick Usage | `validator.go` exported API | Validate function signature |
| API Overview | `validator.go`, `error.go` | Exported types |
| Built-in Rules | `rules.go` | Registered rule names |
| Benchmarks | `validator_test.go` | Benchmark functions exist |
| Testing | `go.mod` | Standard Go test commands |
| License | `LICENSE` | Apache-2.0 |
