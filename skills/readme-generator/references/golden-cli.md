# Golden Example: CLI Tool (Template C)

**Repo signals**: `go.mod` (Go 1.22), `cmd/csvtool/main.go`, `Makefile` (build, test, lint), `LICENSE` (MIT), no `.env.example`.

````markdown
![CI](https://github.com/acme/csvtool/actions/workflows/ci.yml/badge.svg)
![Go](https://img.shields.io/badge/Go-1.22-blue)

# csvtool

Command-line CSV transformer — filter, sort, aggregate, and convert CSV files.

## Installation

```bash
# from source
go install github.com/acme/csvtool/cmd/csvtool@latest

# or build locally
make build              # → ./bin/csvtool
```

## Quick Start

```bash
# filter rows where age > 30, output as JSON
csvtool filter --where "age > 30" --format json data.csv

# output:
# data_filtered.json written (142 rows)
```

```bash
# sort by name, keep top 10
csvtool sort --by name --limit 10 data.csv -o top10.csv

# output:
# top10.csv written (10 rows)
```

## Commands

| Command | Description |
|---------|-------------|
| `filter` | Filter rows by expression |
| `sort` | Sort by column(s) |
| `aggregate` | Group-by aggregation (sum, avg, count) |
| `convert` | Convert between CSV, JSON, TSV |
| `schema` | Print column names and types |

## Flags

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--input` | `-i` | stdin | Input file path |
| `--output` | `-o` | stdout | Output file path |
| `--format` | `-f` | `csv` | Output format (csv/json/tsv) |
| `--where` | `-w` | — | Filter expression |
| `--by` | `-b` | — | Sort column |
| `--limit` | `-l` | all | Max rows in output |
| `--header` | — | `true` | First row is header |

## Common Commands

```bash
make build              # build binary → ./bin/csvtool
make test               # run all tests
make lint               # golangci-lint
make release            # goreleaser build
```

> Command source: root `Makefile`.

## Testing

```bash
make test               # unit tests
go test -race ./...     # with race detection
```

## License

MIT — see [LICENSE](LICENSE).

## Documentation Maintenance

Update this README when:
- New subcommands are added
- Flags change
- Output format options change
````

**Evidence mapping (assistant response)**:

| README Section | Evidence File(s) | Reason |
|---|---|---|
| Badges | `.github/workflows/ci.yml`, `go.mod` | CI workflow, Go 1.22 |
| Installation | `go.mod` module path, `Makefile` (build target) | Standard install paths |
| Quick Start | `cmd/csvtool/main.go` | CLI entrypoint exists |
| Commands/Flags | `cmd/csvtool/main.go` flag definitions | Flag parsing code |
| Commands | `Makefile` | Build/test/lint targets |
| License | `LICENSE` | MIT |
