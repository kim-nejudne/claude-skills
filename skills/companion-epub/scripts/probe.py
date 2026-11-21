"""Print the layout facts epub-settings.json needs, for a split book.

Usage: uv run --with pymupdf python probe.py BOOKDIR

Sections: scan or born-digital; font sizes by share of characters; running heads and folios
(top/bottom lines); small spans (superscripts, note markers, fraction parts); line-end hyphen
kinds; display type on opening pages; vector figures; the first lines of notes pages; the
bottom lines of body pages (footnotes). Read it next to a few rendered pages.
"""
import collections
import json
import re
import sys
from pathlib import Path

import pymupdf


def spans_of(page):
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if s["text"].strip():
                    yield l, s


def lines_of(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            t = "".join(s["text"] for s in l["spans"])
            if t.strip():
                sizes = collections.Counter()
                for s in l["spans"]:
                    sizes[round(s["size"], 1)] += len(s["text"].strip())
                out.append((l["bbox"], t, sizes.most_common(1)[0][0], l["spans"]))
    return sorted(out, key=lambda x: x[0][1])


def main(bookdir: Path):
    m = json.loads((bookdir / "chapters/.parts.json").read_text())
    doc = pymupdf.open(bookdir / m["source_pdf"])
    parts = m["parts"]
    body = [p for part in parts for p in range(part["body"][0], part["body"][1] + 1)]
    notes = [p for part in parts if part.get("notes") for p in range(part["notes"][0], part["notes"][1] + 1)]
    sample = body[:: max(1, len(body) // 60)]
    print(f"pages {len(doc)}  body pages {len(body)}  notes pages {len(set(notes))}")
    print(f"page size {doc[body[0] - 1].rect}")

    scanned = sum(any(b["type"] == 1 and (b["bbox"][2] - b["bbox"][0]) > 0.8 * doc[p - 1].rect.width
                      for b in doc[p - 1].get_text("dict")["blocks"]) for p in sample)
    print(f"\n## scan: {scanned}/{len(sample)} sampled body pages carry a full-page image"
          f"{' -> OCR text layer: sizes jitter, expect OCR typos' if scanned > len(sample) / 2 else ''}")

    for label, pages in (("body", body), ("notes", sorted(set(notes)))):
        if not pages:
            continue
        sizes, fonts = collections.Counter(), collections.defaultdict(collections.Counter)
        for p in pages[:: max(1, len(pages) // 60)]:
            for _, s in spans_of(doc[p - 1]):
                k = round(s["size"] * 2) / 2
                sizes[k] += len(s["text"])
                fonts[k][s["font"].split("+")[-1]] += len(s["text"])
        total = sum(sizes.values())
        print(f"\n## {label} font sizes (0.5 pt bins, share of characters)")
        for k in sorted(sizes):
            if sizes[k] / total > 0.002:
                print(f"  {k:5.1f}  {100 * sizes[k] / total:5.1f}%  {', '.join(f for f, _ in fonts[k].most_common(3))}")

    print("\n## top and bottom lines of sampled body pages (y0, size, text)")
    for p in sample[:12]:
        ls = lines_of(doc[p - 1])
        if ls:
            t, b = ls[0], ls[-1]
            print(f"  p{p:<4} top {t[0][1]:6.1f} {t[2]:4.1f} {t[1].strip()[:45]!r:50}  "
                  f"bottom {b[0][1]:6.1f} {b[2]:4.1f} {b[1].strip()[:30]!r}")

    print("\n## small spans in body (< 75% of the commonest size): note markers, superscripts, fractions")
    common = collections.Counter()
    for p in sample:
        for _, s in spans_of(doc[p - 1]):
            common[round(s["size"], 1)] += len(s["text"])
    main_size = common.most_common(1)[0][0]
    small = collections.Counter()
    for p in body:
        for _, s in spans_of(doc[p - 1]):
            if s["size"] < 0.75 * main_size:
                small[(round(s["size"], 1), "digits" if s["text"].strip().isdigit() else s["text"].strip()[:12])] += 1
    for (sz, t), n in small.most_common(15):
        print(f"  {sz:4.1f}  {t!r:16} x{n}")
    glued = sum(len(re.findall(r"[a-z.,;:\"'’”)](\d{1,3})(?=\s|$)", ln[1])) for p in sample for ln in lines_of(doc[p - 1]))
    print(f"  digits glued after a word or punctuation in sampled lines (OCR'd markers?): {glued}")
    stars = sum(ln[1].count("*") for p in body for ln in lines_of(doc[p - 1]))
    print(f"  asterisks in body text: {stars}")

    ends = collections.Counter()
    for p in sample:
        for ln in lines_of(doc[p - 1]):
            t = ln[1].rstrip()
            ends["soft \\xad" if t.endswith("\xad") else "plain -" if t.endswith("-") else "other"] += 1
    print(f"\n## line ends in sampled body: {dict(ends)}")

    print("\n## display type on each part's first page (size >= 1.3 x body)")
    for part in parts:
        p = part["body"][0]
        big = [(round(s["size"], 1), s["text"].strip()[:30]) for _, s in spans_of(doc[p - 1]) if s["size"] >= 1.3 * main_size]
        print(f"  p{p:<4} {part['file'][:30]:30} {big[:5]}")
    print("\n## first 7 lines of each part's first page (y0, size, text): set opening_skip_y below the title block")
    for part in parts:
        p = part["body"][0]
        print(f"  p{p} {part['file']}")
        for bbox, t, sz, _ in lines_of(doc[p - 1])[:7]:
            print(f"      {bbox[1]:6.1f} {sz:4.1f} {t.strip()[:60]!r}")

    figs = [p for p in body + notes
            if any(d["rect"].width > 40 and d["rect"].height > 30 for d in doc[p - 1].get_drawings())]
    print(f"\n## pages with vector drawings > 40x30 pt (become figures): {figs[:40]}")

    if notes:
        print("\n## first lines of the first notes pages (y0, size, font, text)")
        for p in sorted(set(notes))[:2]:
            for bbox, t, sz, sp in lines_of(doc[p - 1])[:14]:
                print(f"  p{p:<4} {bbox[1]:6.1f} {sz:4.1f} {sp[0]['font'].split('+')[-1][:20]:20} {t.strip()[:60]!r}")

    print("\n## bottom 4 lines of sampled body pages (footnotes?)")
    for p in sample[2:8]:
        for bbox, t, sz, sp in lines_of(doc[p - 1])[-4:]:
            print(f"  p{p:<4} x{bbox[0]:6.1f} y{bbox[1]:6.1f} {sz:4.1f} {t.strip()[:60]!r}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]).resolve())
