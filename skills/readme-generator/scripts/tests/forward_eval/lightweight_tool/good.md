# logparser

Internal tool for parsing and summarizing structured JSON log files.

## Quick Start

```bash
go run . --input /var/log/app/app.log --since 1h
```

> Command source: `go run` (no Makefile in repo).

## Common Commands

```bash
go build -o logparser .
go test ./...
go vet ./...
```

## Project Structure

| Path | Purpose |
|------|---------|
| `main.go` | CLI entrypoint and flag parsing |
| `parser.go` | Log line parsing logic |
| `parser_test.go` | Unit tests |

## Testing

```bash
go test ./...
go test -race ./...
```

## Documentation Maintenance

Update this README when:

- new flags or subcommands are added
- the supported log format changes
- dependencies are added
