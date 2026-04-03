"""
MkDocs hook: inject landing-page templates without touching the source markdown.

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
frontmatter (they render on GitHub too), so the template assignment happens
here via the hook instead.
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


def on_page_markdown(markdown, page, config, files):
    """
    Set template BEFORE MkDocs calls get_template(env, page).
    on_page_context fires after template selection, so it is too late.
    on_page_markdown fires after read_source (page.meta is populated)
    but before the template is resolved — the right moment.
    """
    template = TEMPLATE_MAP.get(page.file.src_path)
    if template:
        page.meta["template"] = template
    return markdown