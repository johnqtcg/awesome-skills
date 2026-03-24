# Quality Gate: Rust

Marker: `Cargo.toml` in the repo root.

## Lint

```bash
cargo clippy -- -D warnings
```

## Tests

Determine scope by checking for workspace:

```bash
# Workspace if [workspace] section exists in root Cargo.toml
IS_WORKSPACE=$(grep -c '^\[workspace\]' Cargo.toml 2>/dev/null || echo 0)
```

- **Single-crate** (`IS_WORKSPACE` = 0): `cargo test`
- **Workspace** (`IS_WORKSPACE` > 0): test only affected crates.
  ```bash
  CHANGED_CRATES=$(git diff --cached --name-only -- '*.rs' | while read -r f; do
    d=$(dirname "$f")
    while [ "$d" != "." ]; do
      [ -f "$d/Cargo.toml" ] && echo "$d" && break
      d=$(dirname "$d")
    done
  done | sort -u)
  for crate in $CHANGED_CRATES; do
    cargo test --manifest-path "$crate/Cargo.toml"
  done
  ```