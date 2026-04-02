"""
MkDocs hook: inject landing-page templates without touching the source markdown.

docs/index.md    → home.html
docs/index-zh.md → home-zh.html

Both files are symlinks to README.md / README.zh-CN.md, which are also
shown on GitHub, so frontmatter must not be added to those files.
"""


def on_page_markdown(markdown, page, config, files):
    """
    Set template BEFORE MkDocs calls get_template(env, page).
    on_page_context fires after template selection, so it is too late.
    on_page_markdown fires after read_source (page.meta is populated)
    but before the template is resolved — the right moment.
    """
    if page.file.src_path == "index.md":
        page.meta["template"] = "home.html"
    elif page.file.src_path == "index-zh.md":
        page.meta["template"] = "home-zh.html"
    return markdown