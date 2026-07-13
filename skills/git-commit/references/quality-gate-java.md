# Quality Gate: Java / Kotlin

Marker: `pom.xml` or `build.gradle` / `build.gradle.kts` in the repo root.

**Manifest changes are project-wide.** The module scoping below selects ZERO modules for a stage that only touches `pom.xml`/Gradle files — a silent no-op gate. Check first:

```bash
MANIFEST_CHANGED=$(git diff --cached --name-only -- 'pom.xml' '*/pom.xml' \
  '*.gradle' '*.gradle.kts' \
  'gradle.properties' '*/gradle.properties' 'gradle.lockfile' '*/gradle.lockfile' \
  | wc -l | tr -d ' ')
# `*.gradle` / `*.gradle.kts` match build.gradle AND settings.gradle(.kts) at any depth.
```

- `MANIFEST_CHANGED` > 0 → run the root gate (`mvn test -q` / `./gradlew test`) and skip module scoping — a dependency bump can break any module.
- **Empty-set rule**: if the scoped module set below comes out empty for ANY reason (root-module sources, files the ancestor walk cannot map), run the root full gate — an empty selection must never mean "no tests" (silent no-op gate).

## Maven

Determine scope by checking for multi-module structure:

```bash
# Check if this is a multi-module project (parent pom with <modules>)
MODULE_COUNT=$(grep -c '<module>' pom.xml 2>/dev/null || true); MODULE_COUNT=${MODULE_COUNT:-0}
# (`grep -c` prints 0 AND exits 1 on no match; `|| echo 0` would append a second line
#  and break the numeric compare below. `|| true` + default keeps it a single value.)
```

- **Single-module** (`MODULE_COUNT` = 0): `mvn test -q`
- **Multi-module** (`MODULE_COUNT` > 0): test only affected modules.
  ```bash
  # Find the nearest pom.xml ancestor for each staged Java/Kotlin file
  CHANGED_MODULES=$(git diff --cached --name-only -- '*.java' '*.kt' '*.kts' | while read -r f; do
    d=$(dirname "$f")
    while [ "$d" != "." ]; do
      [ -f "$d/pom.xml" ] && echo "$d" && break
      d=$(dirname "$d")
    done
  done | sort -u | paste -sd,)
  if [ -n "$CHANGED_MODULES" ]; then
    mvn test -pl "$CHANGED_MODULES" -am -q
  else
    mvn test -q   # empty-set rule: unmapped/root sources → full run, never a no-op
  fi
  ```
  Note: `-am` (also-make) ensures dependencies of changed modules are built first.

## Gradle

- **Single-module**: `./gradlew test`
- **Multi-module**: identify changed subprojects and test each:
  ```bash
  CHANGED_PROJECTS=$(git diff --cached --name-only -- '*.java' '*.kt' '*.kts' | while read -r f; do
    d=$(dirname "$f")
    while [ "$d" != "." ]; do
      [ -f "$d/build.gradle" ] || [ -f "$d/build.gradle.kts" ] && echo "$d" && break
      d=$(dirname "$d")
    done
  done | sort -u | sed 's|/|:|g; s|^|:|')
  if [ -n "$CHANGED_PROJECTS" ]; then
    for proj in $CHANGED_PROJECTS; do
      ./gradlew "${proj}:test"
    done
  else
    ./gradlew test   # empty-set rule: unmapped/root sources → full run, never a no-op
  fi
  ```