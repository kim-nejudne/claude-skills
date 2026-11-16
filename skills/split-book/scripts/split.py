"""Split a book PDF into per-unit PDFs from a parts manifest.

Usage: uv run --with pikepdf python split.py book.pdf chapters/.parts.json

The manifest's "parts" list gives each unit's output "file", "title", "body"
[first, last] and optional "notes" [first, last]: 1-based, inclusive PDF pages.
Output PDFs go next to the manifest, with Title/Author set in docinfo and XMP.
"""
import json
import sys
from pathlib import Path

import pikepdf


def page_list(part: dict) -> list[int]:
    pages = list(range(part["body"][0], part["body"][1] + 1))
    if part.get("notes"):
        pages += range(part["notes"][0], part["notes"][1] + 1)
    return pages


def main() -> None:
    src_path, manifest_path = Path(sys.argv[1]), Path(sys.argv[2])
    m = json.loads(manifest_path.read_text())
    out_dir = manifest_path.parent
    with pikepdf.open(src_path) as src:
        n = len(src.pages)
        for part in m["parts"]:
            pages = page_list(part)
            assert pages and all(1 <= p <= n for p in pages), f"{part['file']}: pages outside 1–{n}"
            assert part["body"][0] <= part["body"][1], f"{part['file']}: body range reversed"
            title = f"{m['title']} — {part['title']}"
            out = pikepdf.new()
            for p in pages:
                out.pages.append(src.pages[p - 1])
            out.docinfo["/Title"] = title
            out.docinfo["/Author"] = m["author"]
            with out.open_metadata(set_pikepdf_as_editor=False) as meta:
                meta["dc:title"] = title
                meta["dc:creator"] = [m["author"]]
            assert len(out.pages) == len(pages)
            out.save(out_dir / part["file"])
            print(f"{part['file']}: {len(pages)} pages")


if __name__ == "__main__":
    main()
