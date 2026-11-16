"""Render reading-companion Markdown to PDF.

Usage:
    uv run --quiet --with markdown python ~/.claude/skills/reading-companion/scripts/build.py companions/src/*.md
PDFs land in the parent of each file's src/ folder (companions/).

Book-wide settings come from book.json next to the .md files:
    {"book": "...", "author": "...", "accent": "#RRGGBB", "accent_soft": "#RRGGBB"}
Each .md starts with python-markdown `meta` headers:
    Title, Subtitle, Eyebrow, Running, Pages, Citation
"""
import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

CSS = (Path(__file__).resolve().parent / "style.css").read_text()


def render(md_path: Path) -> Path:
    book = json.loads((md_path.parent / "book.json").read_text())
    md = markdown.Markdown(extensions=["meta", "extra", "sane_lists"])
    text = re.sub(r"\b(pp?\.|nn?\.) (?=\d)", "\\1\u00a0", md_path.read_text())  # keep "p. 53" on one line
    body = md.convert(text)
    meta = {k: " ".join(v) for k, v in md.Meta.items()}
    for key in ("title", "running", "pages"):
        if key not in meta:
            sys.exit(f"{md_path.name}: missing meta '{key}'")

    def inline(s: str) -> str:  # allow *italics* in meta values
        return markdown.markdown(s).removeprefix("<p>").removesuffix("</p>")

    masthead = f"""
<header class="masthead">
  <p class="eyebrow">{html.escape(meta.get('eyebrow', 'Reading companion'))}</p>
  <h1>{inline(meta['title'])}</h1>
  {f'<p class="subtitle">{inline(meta["subtitle"])}</p>' if 'subtitle' in meta else ''}
  <p class="meta"><b><i>{html.escape(book['book'])}</i></b> · {html.escape(book['author'])} · {inline(meta['pages'])}</p>
  {f'<p class="citation">{inline(meta["citation"])}</p>' if 'citation' in meta else ''}
</header>"""
    doc_title = f"{book['book']} — Companion: {meta['running']}"
    accent = book.get("accent", "#7A2E2E")
    page_css = (
        ":root { --accent: %s; --accent-soft: %s; }\n"
        "@page { @bottom-left { content: %s; } @bottom-right { color: %s; } }"
        % (accent, book.get("accent_soft", "#F5ECEA"),
           json.dumps(f"{book['book']} · {meta['running']}", ensure_ascii=False), accent)
    )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{html.escape(doc_title)}</title>
<style>{CSS}
{page_css}</style></head>
<body>{masthead}
{body}
</body></html>"""

    out = md_path.parent.parent / f"{md_path.stem}-companion.pdf"
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "doc.html"
        src.write_text(page)
        subprocess.run(
            ["chromium", "--headless", "--disable-gpu", "--no-pdf-header-footer",
             "--generate-pdf-document-outline",  # bookmarks from the headings
             f"--user-data-dir={tmp}/profile",  # own profile so parallel builds don't collide
             f"--print-to-pdf={out}", src.as_uri()],
            check=True, capture_output=True,
        )
    assert out.exists() and out.stat().st_size > 0, f"no PDF for {md_path.name}"
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for a in sys.argv[1:]:
        print(render(Path(a).resolve()))
