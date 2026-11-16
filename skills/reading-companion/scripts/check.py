"""Check a reading-companion .md against the book: quotes, their pages, page ranges, structure, length.

Usage:
    python3 -I check.py <BOOKDIR>/companions/src/<unit>.md <BOOKDIR>
    python3 -I check.py --selftest

Needs <BOOKDIR>/chapters/.parts.json (from /split-book) and one text file per chapter PDF in
<BOOKDIR>/companions/.text/<stem>.txt (`pdftotext -layout`, which keeps a form feed between pages).

Quotes: blockquotes and inline “…” quotes of 4+ words. Ellipses and [brackets] split a quote into
fragments; each is matched after reducing both sides to lowercase letters and digits (absorbs OCR
spacing, hyphenation and punctuation noise). A found fragment must sit on the page cited in its
`<span class="src">… · p. N</span>`, or in a `(p. N)` right after an inline quote. Hits on book-end
notes pages can't be mapped to a book page, so those are reported as unchecked.

book-overview.md gets the quote checks only. Exit 1 if anything is reported.
"""
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

SECTIONS = ["Context in depth", "Argument map", "Section by section", "Close reading",
            "Key terms", "Who's who", "Key quotations", "Cross-chapter connections"]
PRIMER_PARTS = ['## Before you read', '#### Thesis', '<p class="thesis">', '#### Context you need',
                '#### Watch for', '#### Key terms preview', '<p class="terms-preview">']
DIVS = ['<div class="argument" markdown="1">', '<div class="glossary" markdown="1">',
        '<div class="people" markdown="1">']
PAGES = r"pp?\.\s*(\d+(?:\s*[–-]\s*\d+)?(?:,\s*\d+(?:\s*[–-]\s*\d+)?)*)"
OTHER_UNIT = re.compile(r"(Ch(?:apter|s?\.)\s*\d|Introduction|Prologue|Epilogue|Conclusion|Afterword)")


def norm(s: str) -> str:
    s = re.sub(r"-\s*\n\s*", "", s)  # rejoin words hyphenated across lines
    return re.sub(r"[^a-z0-9]", "", s.lower())


def span(r: str) -> tuple[int, int]:
    """'102–3' -> (102, 103); '219–24' -> (219, 224); '97' -> (97, 97)."""
    a, _, b = re.sub(r"\s", "", r).replace("-", "–").partition("–")
    if not b:
        return int(a), int(a)
    if len(b) < len(a):
        b = a[: len(a) - len(b)] + b
    return int(a), int(b)


def spans(refs: str) -> list[tuple[int, int]]:
    return [span(r) for r in refs.split(",")]


class Book:
    """All chapter texts as one normalised string, with a book page (or None) per character."""

    def __init__(self, bookdir: Path):
        parts = json.loads((bookdir / "chapters/.parts.json").read_text())["parts"]
        chunks, self.starts, self.pages = [], [], []
        pos = 0
        for p in parts:
            txt = bookdir / "companions/.text" / (Path(p["file"]).stem + ".txt")
            if not txt.exists():
                sys.exit(f"missing {txt}: run pdftotext -layout on chapters/{p['file']}")
            body_len = p["body"][1] - p["body"][0] + 1
            for i, page in enumerate(txt.read_text().split("\f")):
                n = norm(page)
                chunks.append(n)
                self.starts.append(pos)
                # body page i is PDF page body[0]+i; notes pages after the body have no known offset
                self.pages.append(p["body"][0] + i - p["page_offset"] if i < body_len else None)
                pos += len(n)
        self.text = "".join(chunks)

    def page_at(self, i: int):
        lo, hi = 0, len(self.starts) - 1
        while lo < hi:  # last start <= i
            mid = (lo + hi + 1) // 2
            lo, hi = (mid, hi) if self.starts[mid] <= i else (lo, mid - 1)
        return self.pages[lo]

    def find(self, n: str) -> list[tuple]:
        """(first page, last page) of every occurrence of normalised fragment n."""
        hits, i = [], self.text.find(n)
        while i != -1:
            hits.append((self.page_at(i), self.page_at(i + len(n) - 1)))
            i = self.text.find(n, i + 1)
        return hits


def quotes(md: str) -> list[tuple[str, list | None]]:
    """(quote, cited page spans or None) for every blockquote and inline quote of 4+ words."""
    md = re.sub(r'<span class="hint">.*?</span>', " ", md)
    found, block = [], []
    for line in md.splitlines() + [""]:
        if line.startswith(">"):
            block.append(line.lstrip("> "))
        elif block:
            q = " ".join(block)
            src = re.search(r'<span class="src">(.*?)</span>', q)
            cites = re.findall(PAGES, src.group(1)) if src else []
            q = re.sub(r'<span class="src">.*?</span>', " ", q)
            found.append((re.sub(r"<[^>]+>", " ", q), [s for c in cites for s in spans(c)] or None))
            block = []
    flat = re.sub(r"<[^>]+>", " ", re.sub(r'<span class="src">.*?</span>', " ", md))
    flat = "\n".join(l for l in flat.splitlines() if not l.startswith(">"))
    for m in re.finditer(r"“([^”]+)”", flat):
        if len(m.group(1).split()) < 4:
            continue
        cite = re.match(r"[,.;:]?\s*\(" + PAGES, flat[m.end():m.end() + 30])
        found.append((m.group(1), spans(cite.group(1)) if cite else None))
    return found


def check_quotes(md: str, book: Book) -> list[str]:
    out = []
    for q, cited in quotes(md):
        q = re.sub(r"—\s*pp?\.\s*[\d–-]+.*$", "", q)  # drop trailing page cite
        for frag in re.split(r"\.\s?\.\s?\.|…|\[[^\]]*\]", q):
            n = norm(frag)
            if len(frag.split()) < 3:
                continue
            hits = book.find(n)
            if not hits:
                m = SequenceMatcher(None, n, book.text, autojunk=False).find_longest_match(
                    0, len(n), 0, len(book.text))
                out.append(f"MISS ({m.size / len(n):.0%} longest run): {frag.strip()[:110]}")
            elif cited and not any(a is not None and b is not None and a <= hi and b >= lo
                                   for a, b in hits for lo, hi in cited):
                where = sorted({a for a, _ in hits if a is not None})
                if where:
                    out.append(f"WRONG PAGE (cited {cited}, found on {where}): {frag.strip()[:90]}")
                else:
                    out.append(f"UNCHECKED (found only in book-end notes): {frag.strip()[:90]}")
    return out


def meta(md: str) -> dict:
    m = {}
    for line in md.splitlines():
        if not line.strip():
            break
        k, _, v = line.partition(":")
        m[k.strip().lower()] = v.strip()
    return m


def target(pages_meta: str) -> tuple[int, int]:
    ranges = re.findall(PAGES, pages_meta)
    a, b = spans(ranges[0])[0]
    n = b - a + 1
    if n < 15:
        return 1600, 2000
    t = min(max(2000 + 50 * n, 2800), 4500)
    return round(t * 0.85), round(t * 1.15)


def check_unit(md: str) -> list[str]:
    out = []
    m = meta(md)
    for k in ("title", "eyebrow", "running", "pages", "citation"):
        if k not in m:
            out.append(f"STRUCTURE: missing meta '{k}'")
    if '<section class="primer" markdown="1">' not in md:
        out.append('STRUCTURE: missing <section class="primer" markdown="1">')
    out += [f"STRUCTURE: primer lacks {p}" for p in PRIMER_PARTS if p not in md]
    out += [f"STRUCTURE: missing {d}" for d in DIVS if d not in md]
    heads = [h.replace("’", "'") for h in re.findall(r'^## <span class="num">\d+</span> (.+)$', md, re.M)]
    nums = re.findall(r'^## <span class="num">(\d+)</span>', md, re.M)
    if heads != SECTIONS or nums != [str(i) for i in range(1, 9)]:
        out.append(f"STRUCTURE: numbered sections are {list(zip(nums, heads))}, want {SECTIONS}")
    if re.search(r"^>.*\n\s*\n>", md, re.M):
        out.append("STRUCTURE: consecutive blockquotes need a <!-- --> line between them")
    for ch in ("ʿ", "ʾ"):
        if ch in md:
            out.append(f"CHARACTER: U+{ord(ch):04X} found; use ‘ (ʿayn) or ’ (hamza)")

    allowed = [s for r in re.findall(PAGES, m.get("pages", "")) for s in spans(r)]
    cross = md.find('<span class="num">8</span>')
    body = md[md.find('<section class="primer"'):cross if cross != -1 else None]
    for line_no, line in enumerate(body.splitlines(), md[:md.find('<section class="primer"')].count("\n") + 1):
        for mm in re.finditer(PAGES, line):
            if OTHER_UNIT.search(line[max(0, mm.start() - 40):mm.start()]):
                continue
            for a, b in spans(mm.group(1)):
                if not any(lo <= a and b <= hi for lo, hi in allowed):
                    out.append(f"PAGE RANGE: line {line_no}: p. {a}{'' if a == b else f'–{b}'} outside {m.get('pages')}")

    if "pages" in m:
        lo, hi = target(m["pages"])
        words = len(md.split())
        flag = "" if lo <= words <= hi else "  <- adjust"
        print(f"LENGTH: {words} words, target {lo}–{hi}{flag}")
        if flag:
            out.append(f"LENGTH: {words} words outside {lo}–{hi}")
    return out


def selftest() -> None:
    assert span("102–3") == (102, 103) and span("219–24") == (219, 224) and span("97") == (97, 97)
    assert spans("93, 100") == [(93, 93), (100, 100)]
    assert target("Chapter pp. 27–54") == (round(3400 * .85), round(3400 * 1.15))
    assert target("Prologue pp. 1–8") == (1600, 2000)
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "chapters").mkdir()
        (d / "companions/.text").mkdir(parents=True)
        (d / "chapters/.parts.json").write_text(json.dumps({"parts": [
            {"file": "01-a.pdf", "body": [10, 11], "notes": [30, 30], "page_offset": 9}]}))
        (d / "companions/.text/01-a.txt").write_text(
            "alpha beta gamma delta\fepsilon zeta eta theta\fnote iota kappa lambda")
        b = Book(d)
        assert b.find(norm("alpha beta gamma")) == [(1, 1)]
        assert b.find(norm("epsilon zeta eta")) == [(2, 2)]
        assert b.find(norm("delta epsilon zeta")) == [(1, 2)]  # spans a page break
        assert b.find(norm("iota kappa lambda")) == [(None, None)]  # notes page
        md = '> “epsilon zeta eta theta”\n> <span class="src">X · p. 1</span>\n\nSee “alpha beta gamma delta” (p. 1).\n'
        res = check_quotes(md, b)
        assert len(res) == 1 and res[0].startswith("WRONG PAGE"), res
    print("selftest ok")


def main() -> int:
    if sys.argv[1:] == ["--selftest"]:
        selftest()
        return 0
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    md_path, bookdir = Path(sys.argv[1]), Path(sys.argv[2])
    md = md_path.read_text()
    out = check_quotes(md, Book(bookdir))
    if md_path.name != "book-overview.md":
        out += check_unit(md)
    print("\n".join(out))
    print(f"{len(out)} problem(s)")
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main())
