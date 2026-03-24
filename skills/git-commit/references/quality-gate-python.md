# Quality Gate: Python

Marker: `pyproject.toml`, `setup.py`, or `setup.cfg` in the repo root.

## Lint

Prefer `ruff check .` if available; fall back to `flake8`.

## Type Check

Run `mypy` or `pyright` if either is installed or listed in dev dependencies.

## Tests

Determine scope by counting changed Python files:

```bash
CHANGED_PY=$(git diff --cached --name-only -- '*.py')
CHANGED_COUNT=$(echo "$CHANGED_PY" | grep -c '.' || true)
```

- **<= 30 changed files**: `pytest`.
- **> 30 changed files**:
  - **With pytest-testmon** (preferred — tracks test-to-source mapping automatically):
    ```bash
    pytest --testmon
    ```
  - **Without pytest-testmon**: discover matching test files from changed source files, then run:
    ```bash
    # Map source files to their test counterparts
    TEST_FILES=""
    for src in $CHANGED_PY; do
      # Skip files already in test directories
      echo "$src" | grep -qE '(^|/)tests?/' && TEST_FILES="$TEST_FILES $src" && continue
      # Convert src/foo/bar.py → tests/foo/test_bar.py or tests/test_bar.py
      base=$(basename "$src" .py)
      dir=$(dirname "$src")
      stripped_dir=$(echo "$dir" | sed 's|^src/||')
      for candidate in \
        "${dir}/test_${base}.py" \
        "${dir}/${base}_test.py" \
        "tests/test_${base}.py" \
        "tests/${dir}/test_${base}.py" \
        "tests/${stripped_dir}/test_${base}.py"; do
        [ -f "$candidate" ] && TEST_FILES="$TEST_FILES $candidate" && break
      done
    done
    if [ -n "$TEST_FILES" ]; then
      pytest $TEST_FILES
    else
      pytest  # fallback to full suite if no test files found
    fi
    ```
- If `pyproject.toml` has a `[tool.pytest]` or `[tool.tox]` section, respect that config.