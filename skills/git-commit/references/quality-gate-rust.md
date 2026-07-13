# Quality Gate: Rust

Marker: `Cargo.toml` in the repo root.

## Lint

```bash
cargo clippy -- -D warnings
```

## Tests

**Manifest/lockfile changes are workspace-wide.** Scoping by changed `.rs` files selects ZERO crates for a `Cargo.toml`/`Cargo.lock`-only stage — a silent no-op gate. Check first:

```bash
MANIFEST_CHANGED=$(git diff --cached --name-only -- 'Cargo.toml' '*/Cargo.toml' 'Cargo.lock' | wc -l | tr -d ' ')
```

- `MANIFEST_CHANGED` > 0 → run the full suite (`cargo test --workspace`; single crate: `cargo test`) and skip the changed-crate scoping below — a dependency or feature-flag change can break any crate.

Otherwise determine scope by checking for workspace:

```bash
# Workspace if [workspace] section exists in root Cargo.toml
IS_WORKSPACE=$(grep -c '^\[workspace\]' Cargo.toml 2>/dev/null || true); IS_WORKSPACE=${IS_WORKSPACE:-0}
# (`grep -c` prints 0 AND exits 1 on no match; `|| echo 0` would append a second line
#  and break the numeric compare. `|| true` + default keeps it a single value.)
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
  if [ -n "$CHANGED_CRATES" ]; then
    for crate in $CHANGED_CRATES; do
      cargo test --manifest-path "$crate/Cargo.toml"
    done
  else
    cargo test --workspace   # empty-set rule: unmapped/root sources → full run, never a no-op
  fi
  ```