# Quality Gate: Java / Kotlin

Marker: `pom.xml` or `build.gradle` / `build.gradle.kts` in the repo root.

## Maven

Determine scope by checking for multi-module structure:

```bash
# Check if this is a multi-module project (parent pom with <modules>)
MODULE_COUNT=$(grep -c '<module>' pom.xml 2>/dev/null || echo 0)
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
  for proj in $CHANGED_PROJECTS; do
    ./gradlew "${proj}:test"
  done
  ```