# Golden Example: CLI Tool (Template C)

**Repo signals**: `go.mod` (Go 1.22) · `cmd/csvtool/main.go` with a `cobra` command tree
(`filter sort aggregate convert schema`) and its flag definitions · `Makefile` targets
`build test lint release` · `.github/workflows/ci.yml` · `LICENSE` (MIT) · no `.env.example` ·
no committed sample output.

The last signal is why the Quick Start below shows invocations and destinations but never a
row count or a rendered result.

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
# filter rows where age > 30, write JSON
csvtool filter --where "age > 30" --format json data.csv
# → writes data_filtered.json
```

```bash
# sort by name, keep the first 10 rows
csvtool sort --by name --limit 10 data.csv -o top10.csv
# → writes top10.csv
```

The destination file is evidence (the flag parser defines `-o`); the row count is not — it
depends on the input file, which the repo does not ship.

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
