"""Print what is needed to find a fiction EPUB's body units.

Usage: uv run --quiet --with lxml python -I probe.py book.epub

Prints: title, author, language; the spine, one block per file (words, epub:type of body and
sections, every heading with the nearest id, the first text line); the nav table of contents with
hrefs. Paths are relative to the OPF folder, as the manifest's "src" files must be.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ in the dotfiles repo
sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script's folder off sys.path
from epubsrc import X, Source, etypes, text, words  # noqa: E402

HEADS = [f"{{{X}}}h{i}" for i in range(1, 7)]


def main(path: str):
    s = Source(path)
    print(f"TITLE {s.title}\nAUTHOR {s.author}\nLANG {s.lang}\nSPINE {len(s.spine)} files")
    print("\n== SPINE (file | words | epub:type)\n   headings: <tag> #<nearest id> text")
    for href in s.spine:
        body = s.body(href)
        if body is None:
            print(f"{href} | no body")
            continue
        t = text(body)
        types = sorted({" ".join(sorted(etypes(e))) for e in [body, *body.iter(f"{{{X}}}section")] if etypes(e)})
        print(f"\n{href} | {len(words(t))} words | {'; '.join(types) or '-'}")
        for h in body.iter(*HEADS):
            ident = h.get("id")
            anc = h
            while ident is None and anc is not None and anc is not body:  # a heading's section usually holds the id
                anc = anc.getparent()
                ident = anc.get("id") if anc is not None else None
            label = " ".join("".join(h.itertext()).split())[:90]
            print(f"   <{h.tag.split('}')[1]}> #{ident or '-'} {label}")
        first = next((p for p in t.split("\n\n") if len(p) > 40), t[:100])
        print(f"   first: {first[:120]}")
    print("\n== NAV (depth, label, href)")
    for depth, label, href in s.nav():
        print(f"{'  ' * depth}{label[:70]}  ->  {href}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
