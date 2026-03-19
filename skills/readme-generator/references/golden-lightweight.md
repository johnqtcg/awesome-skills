# Golden Example: Lightweight (Template E)

**Repo signals**: 3 Go files, `go.mod` (Go 1.22), no Makefile, no CI, no `.env.example`, no LICENSE. Internal tool for log parsing.

````markdown
# logparser

Internal tool for parsing and summarizing structured JSON log files.

## Quick Start

```bash
go run . --input /var/log/app/app.log --since 1h
```

> Command source: `go run` (no Makefile in repo).

## Common Commands

```bash
go build -o logparser .     # build binary
go test ./...               # run tests
go vet ./...                # static analysis
```

## Project Structure

```
logparser/
├── main.go                 # CLI entrypoint and flag parsing
├── parser.go               # Log line parsing logic
├── parser_test.go          # Unit tests
└── go.mod                  # Go 1.22
```

## Testing

```bash
go test ./...               # 12 tests, ~95% coverage
go test -race ./...         # race detection
```

## Documentation Maintenance

Update this README when:
- New flags or subcommands are added
- Log format support changes
- Dependencies are added
````

**Evidence mapping (assistant response)**:

| README Section | Evidence File(s) | Reason |
|---|---|---|
| Quick Start | `main.go` (flag parsing) | CLI entrypoint |
| Commands | `go.mod` | Standard Go toolchain (no Makefile) |
| Structure | `main.go`, `parser.go`, `parser_test.go` | 3 Go files |
| Testing | `parser_test.go` | Test file exists |
| Badges | Not applicable | No CI, private repo |

**Note**: This example uses Lightweight Template Mode — the repo has < 5 directories, no CI, no public API. Heavy sections (Badges, Architecture, Deployment, API, License) are omitted.
