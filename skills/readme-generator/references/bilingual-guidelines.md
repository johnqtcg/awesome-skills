# Chinese / Bilingual README Guidelines

Load this file when the output language is Chinese or bilingual (detected from existing repo docs, user request, or code comments language).

## Language Split Rules

- **Keep English for**: package names, command names, file paths, environment variable names, technical terms with no standard translation (e.g., `goroutine`, `middleware`, `webhook`).
- **Translate to Chinese**: section headings, explanatory prose, comments, workflow descriptions.
- **Bilingual mode**: use Chinese as primary with English technical terms inline. Do not duplicate full sections in both languages.
- **Section heading style**: `## 快速开始` (not `## Quick Start / 快速开始` — avoid double headings).
- **Command blocks**: keep commands in English, add Chinese comments above when the command is non-obvious.

## Example

```markdown
## 快速开始

安装依赖并启动服务：

```bash
make install-tools
make run-api
```
```

## Anti-patterns to Avoid

See `references/anti-examples.md` → "Double-language headings" for the full BAD/GOOD pair.
