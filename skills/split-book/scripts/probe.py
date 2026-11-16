"""Print what is needed to find a book's chapter boundaries.

Usage: uv run --with pikepdf python probe.py book.pdf [--lines N]

Prints: page count; outline (bookmarks) with 1-based PDF pages; page labels;
then one row per page: PDF page, label, text characters, first N text lines
(running heads and printed page numbers). Pages with few characters suggest
no text layer.
"""
import subprocess
import sys

import pikepdf


def outline(pdf: pikepdf.Pdf) -> list[tuple[int, str, int | None]]:
    rows = []
    named = None
    if "/Names" in pdf.Root and "/Dests" in pdf.Root.Names:
        named = pikepdf.NameTree(pdf.Root.Names.Dests)
    elif "/Dests" in pdf.Root:
        named = pdf.Root.Dests
    with pdf.open_outline() as ol:
        def walk(items, depth):
            for it in items:
                page = None
                try:
                    dest = it.destination
                    if dest is None and it.action is not None and "/D" in it.action:
                        dest = it.action.D
                    if dest is not None and not isinstance(dest, pikepdf.Array):  # named destination
                        dest = named.get(str(dest)) if named is not None else None
                        if isinstance(dest, pikepdf.Dictionary):
                            dest = dest.D
                    if isinstance(dest, pikepdf.Array) and len(dest):
                        page = pikepdf.Page(dest[0]).index + 1
                except Exception:  # unresolvable entry: print with "?"
                    pass
                rows.append((depth, it.title, page))
                walk(it.children, depth + 1)
        walk(ol.root, 0)
    return rows


def main() -> None:
    path = sys.argv[1]
    n_lines = int(sys.argv[sys.argv.index("--lines") + 1]) if "--lines" in sys.argv else 2
    pdf = pikepdf.open(path)
    n = len(pdf.pages)
    print(f"PAGES {n}")
    print(f"TITLE {pdf.docinfo.get('/Title', '')}  AUTHOR {pdf.docinfo.get('/Author', '')}")

    print("\n== OUTLINE (depth, PDF page, title)")
    rows = outline(pdf)
    for depth, title, page in rows:
        print(f"{'  ' * depth}{page if page else '?':>4}  {title}")
    if not rows:
        print("(none)")

    labels = [p.label for p in pdf.pages] if "/PageLabels" in pdf.Root else None
    print(f"\n== PAGE LABELS {'present' if labels else 'absent'}")

    print("\n== PER PAGE (PDF page | label | chars | first lines)")
    text = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, check=True).stdout
    pages = text.split("\f")[:n]
    for i, t in enumerate(pages, 1):
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
        label = labels[i - 1] if labels else ""
        print(f"{i:>4} | {label:>6} | {len(t.strip()):>5} | {' // '.join(lines[:n_lines])[:140]}")
    empty = sum(1 for t in pages if len(t.strip()) < 200)
    print(f"\nLOW-TEXT PAGES (<200 chars): {empty}/{n}")


if __name__ == "__main__":
    main()
