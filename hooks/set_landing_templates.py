"""
MkDocs hook: inject landing-page templates and per-page meta overrides
without touching the source markdown.

Homepage:
  docs/index.md       → home.html
  docs/index-zh.md    → home-zh.html

Section landing pages:
  bestpractice/README.md       → section-bestpractice.html
  bestpractice/README.zh-CN.md → section-bestpractice-zh.html
  rationale/index.md           → section-rationale.html
  rationale/index.zh-CN.md     → section-rationale-zh.html
  skills/index.md              → section-skills.html
  evaluate/index.md            → section-evaluate.html

Source files are either symlinks (homepages) or stubs that must not carry
frontmatter (they render on GitHub too), so template assignment and meta
overrides happen here via the hook instead.
"""

TEMPLATE_MAP = {
    "index.md":                     "home.html",
    "index-zh.md":                  "home-zh.html",
    "bestpractice/README.md":       "section-bestpractice.html",
    "bestpractice/README.zh-CN.md": "section-bestpractice-zh.html",
    "rationale/index.md":           "section-rationale.html",
    "rationale/index.zh-CN.md":     "section-rationale-zh.html",
    "skills/index.md":              "section-skills.html",
    "evaluate/index.md":            "section-evaluate.html",
}

# Hide the right-sidebar TOC on bestpractice chapter pages.
# These docs have very deep heading hierarchies; the auto-generated TOC is
# too noisy and duplicates information already visible in the page itself.
HIDE_TOC = {
    "bestpractice/Fundamentals.md",
    "bestpractice/Advanced.md",
    "bestpractice/Evaluation.md",
    "bestpractice/Iteration.md",
    "bestpractice/Integration.md",
    "bestpractice/Architecture.md",
    "bestpractice/基础篇.md",
    "bestpractice/进阶篇.md",
    "bestpractice/评估篇.md",
    "bestpractice/迭代篇.md",
    "bestpractice/集成篇.md",
    "bestpractice/架构篇.md",
}


def on_page_markdown(markdown, page, config, files):
    """
    Set template and meta overrides BEFORE MkDocs resolves the template.
    on_page_markdown fires after read_source (page.meta is populated)
    but before template selection — the right moment for both.
    """
    template = TEMPLATE_MAP.get(page.file.src_path)
    if template:
        page.meta["template"] = template

    if page.file.src_path in HIDE_TOC:
        hide = page.meta.setdefault("hide", [])
        if "toc" not in hide:
            hide.append("toc")

    return markdown