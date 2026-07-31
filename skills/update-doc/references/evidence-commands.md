# Evidence Commands Reference

Per-language commands for gathering the code evidence that documentation claims
must trace back to. Load this after `scripts/discover_doc_scope.sh` has reported
`DOMINANT:` — that value selects the block below.

## Regex conventions (read before copying any command)

`rg` uses the Rust regex crate, **not** POSIX basic regular expressions:

- Alternation is a bare `|`. Writing `\|` matches a *literal pipe character*, so
  a pattern like `rg "app\.listen\|createServer"` finds nothing and exits 1 —
  the same exit status as a correct pattern that legitimately has no matches.
  Nothing distinguishes the two, so an unchecked call leaves evidence gathering
  to continue with zero evidence. Never escape the alternation pipe in an `rg`
  pattern.
- `.` must be escaped as `\.` when you mean a literal dot.
- `-l` (files-with-matches) suppresses line output, so combining it with `-n` is
  contradictory. Pick one.

Shell conventions:

- `cmd_a | head -40 || cmd_b` does **not** mean "fall back to `cmd_b`". The `||`
  binds to `head`, which exits 0 even when `cmd_a` produced nothing, so `cmd_b`
  never runs. Use an explicit `if [ -f … ]` chain for manifest fallbacks.

## Go

```bash
# entry points
rg -n "^func main\(" --glob '*.go'

# routes / handlers
rg -n "SetupRoutes|router|app\.(Get|Post|Put|Delete)" --glob '*.go'

# env and config loading
rg -n "os\.Getenv\(|viper\.|godotenv" --glob '*.go'

# dependency manifest
head -20 go.mod
```

## Python

```bash
# entry points
rg -n "^if __name__.*__main__" --glob '*.py'
rg -n "^app = (Flask|FastAPI|Django)" --glob '*.py'

# routes / handlers
rg -n "@(app|router)\.(get|post|put|delete|patch)\(" --glob '*.py'
rg -n "urlpatterns" --glob '*.py'

# env and config loading
rg -n "os\.environ|os\.getenv|dotenv|BaseSettings" --glob '*.py'

# dependency manifest — explicit fallback, not `||`
if [ -f requirements.txt ]; then head -30 requirements.txt
elif [ -f pyproject.toml ]; then head -30 pyproject.toml
fi
```

## Node.js / TypeScript

```bash
# entry points
rg -n '"main"\s*:' package.json
rg -n "app\.listen|createServer|export default" --glob '*.{js,ts}'

# routes / handlers
rg -n "(router|app)\.(get|post|put|delete|patch)\(" --glob '*.{js,ts}'

# env and config loading
rg -n "process\.env\.|dotenv\.config" --glob '*.{js,ts}'

# dependency manifest
head -40 package.json
```

## Java / Spring Boot

```bash
# entry points
rg -n "@SpringBootApplication" --glob '*.java'

# routes / handlers
rg -n "@(GetMapping|PostMapping|PutMapping|DeleteMapping|RequestMapping)" --glob '*.java'

# env and config loading
rg -n "@Value|@ConfigurationProperties" --glob '*.java'
rg -n "^[a-zA-Z].*=" --glob 'application*.properties'
rg -n "^[a-zA-Z]" --glob 'application*.yml'

# dependency manifest — explicit fallback, not `||`
if [ -f pom.xml ]; then grep -A2 '<dependency>' pom.xml | head -40
elif [ -f build.gradle ]; then head -30 build.gradle
elif [ -f build.gradle.kts ]; then head -30 build.gradle.kts
fi
```

## Rust

```bash
# entry points
rg -n "^fn main\(" --glob '*.rs'

# routes / handlers (axum / actix)
rg -n "Router::new|\.route\(|#\[(get|post|put|delete)\(" --glob '*.rs'

# env and config loading
rg -n "std::env::var|envy::|dotenvy" --glob '*.rs'

# dependency manifest
head -40 Cargo.toml
```

## Generic (language-agnostic)

```bash
# entry points — look for common runner patterns
rg -l "main|entrypoint|bootstrap|start" --glob '!*.{md,lock,sum}' | head -10

# env and config loading
rg -n "ENV|CONFIG|DOTENV|\.env" --glob '!*.{md,lock}' | head -20

# dependency manifests
ls requirements.txt pyproject.toml package.json go.mod Cargo.toml pom.xml build.gradle Gemfile 2>/dev/null
```

## Always run (any language)

```bash
# CI/CD workflows
ls .github/workflows 2>/dev/null

# existing docs whose structure must be preserved
ls docs/ README.md CHANGELOG.md 2>/dev/null
```

## Polyglot repositories

When `POLYGLOT: yes`, run the block for each language above its 10% share rather
than only the dominant one, and scope each run to the owning subtree:

```bash
rg -n "^func main\(" --glob 'services/**/*.go'
rg -n "^app = (Flask|FastAPI)" --glob 'services/**/*.py'
```

Document each module against its own language's evidence. A single root-level
command sweep across a polyglot monorepo produces evidence that cannot be mapped
back to the module it describes.
