# acme-tools

![CI](https://github.com/acme/tools/actions/workflows/ci.yml/badge.svg)

Cargo workspace holding the shared parsing core and its command-line front end.

## Repository Overview

| Crate | Path | Description | Docs |
|-------|------|-------------|------|
| core | `crates/core` | Shared parsing types | [README](crates/core/README.md) |
| cli | `crates/cli` | Command-line front end | [README](crates/cli/README.md) |

## Quick Start

```bash
cargo build --workspace
cargo run -p cli
```

## Shared Commands

```bash
cargo build --workspace
cargo test --workspace
cargo clippy --workspace
```

> Command source: Cargo workspace defined in `Cargo.toml`.

## Project Structure

Two crates under `crates`, wired together by the workspace manifest. Each crate's
internal layout is documented in its own README rather than duplicated here.

## Testing

```bash
cargo test --workspace
```

CI runs the same command — see `.github/workflows/ci.yml`.

## Documentation Maintenance

Update this README when:

- a crate is added to or removed from the workspace
- the shared command set changes
- the CI workflow changes
