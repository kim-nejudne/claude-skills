"""Check a fiction companion .md against the book: spoilers, quotes, locators, structure, length.

Usage:
    python3 -I check.py <BOOKDIR>/companions/src/<slug | intro | end>.md <BOOKDIR>
    python3 -I check.py <BOOKDIR>/companions/.digest/<slug>.md <BOOKDIR>       (what happens)
    python3 -I check.py <BOOKDIR>/companions/.digest/<slug>.cast.md <BOOKDIR>  (cast and threads)
    python3 -I check.py --selftest

Needs <BOOKDIR>/companions/.units.json and .text/<slug>.txt (from /fiction-split).

Scope (the text a companion may use):
    novel unit N    units 1..N          collection story   that story only
    intro.md        the first unit      end.md             the whole book (no spoiler checks)
    digest of N     units 1..N

Prints, one per line:
    SPOILER QUOTE   a quote found only outside the scope (a later chapter, another story)
    MISS            a quote found nowhere: misquoted or invented
    LATER WORD      a proper noun (never lowercase in the book, capitalised mid-sentence) the scope never
                    uses but a later unit (another story) does: a leaked name or place, or a
                    harmless coincidence; the checker judges each one. Leaked events in plain
                    words are the checker's job.
    LOCATOR         page, paragraph or chapter numbers beyond the scope, or links
    STRUCTURE       headings, meta, cast list, spoiler banner
    CAST            a novel unit's Characters so far lacks someone in the previous chapter's
                    <slug>.cast.md (the name's words other than titles are not all in the list)
    LENGTH          outside the target (cast list excluded)
Exit 1 if anything is reported.
"""
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

WORD = re.compile(r"[A-Za-z]+(?:[’'][A-Za-z]+)*")
CAST = re.compile(r'<div class="cast" markdown="1">.*?</div>', re.S)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def key(w: str) -> str:
    return re.sub(r"[’']s$", "", w.lower())


def prose_words(md: str) -> int:
    md = re.sub(r"<[^>]+>", " ", md)
    return len(WORD.findall(md))


class Book:
    def __init__(self, bookdir: Path):
        self.dir = bookdir
        self.m = json.loads((bookdir / "companions/.units.json").read_text())
        self.units = self.m["units"]
        self.texts = []
        for u in self.units:
            p = bookdir / "companions/.text" / f"{u['slug']}.txt"
            if not p.exists():
                sys.exit(f"missing {p}: run /fiction-split")
            self.texts.append(p.read_text())
        self.norms = [norm(t) for t in self.texts]
        self.vocab = [{key(w) for w in WORD.findall(t)} for t in self.texts]
        self.lowered = {key(w) for t in self.texts for w in WORD.findall(t) if w[0].islower()}
        # capitalised mid-sentence somewhere: a name, not just a word that happens to open sentences
        self.midcaps = {key(m.group(1)) for t in self.texts
                        for m in re.finditer(r"[a-z,;]\s+([A-Z][a-z]+(?:[’'][a-z]+)*)", t)}
        self.collection = self.m.get("form") == "collection"

    def scope(self, stem: str) -> tuple[str, list[int], int | None]:
        """-> (role, indices in scope, unit index or None)."""
        n = len(self.units)
        if stem == "intro":
            return "intro", [0], None
        if stem == "end":
            return "end", list(range(n)), None
        for i, u in enumerate(self.units):
            if u["slug"] == stem:
                return ("story", [i], i) if self.collection else ("unit", list(range(i + 1)), i)
        sys.exit(f"{stem}: not a unit slug in .units.json, nor intro or end")


def meta(md: str) -> dict:
    m = {}
    for line in md.splitlines():
        if not line.strip():
            break
        k, _, v = line.partition(":")
        m[k.strip().lower()] = v.strip()
    return m


def quotes(md: str) -> list[str]:
    """Blockquotes and inline “…” quotes of 3+ words."""
    found, block = [], []
    for line in md.splitlines() + [""]:
        if line.startswith(">"):
            block.append(line.lstrip("> "))
        elif block:
            found.append(re.sub(r"<[^>]+>", " ", re.sub(r'<span class="src">.*?</span>', " ", " ".join(block))))
            block = []
    flat = "\n".join(l for l in md.splitlines() if not l.startswith(">"))
    flat = re.sub(r"<[^>]+>", " ", flat)
    found += [q for q in re.findall(r"“([^”]+)”", flat) if len(q.split()) >= 3]
    return found


def check_quotes(md: str, book: Book, scope: list[int], spoil: bool) -> list[str]:
    out = []
    inside = "".join(book.norms[i] for i in scope)
    for q in quotes(md):
        for frag in re.split(r"\.\s?\.\s?\.|…|\[[^\]]*\]", q):
            n = norm(frag)
            if len(frag.split()) < 3 or n in inside:
                continue
            where = [book.units[i]["slug"] for i, t in enumerate(book.norms) if n in t]
            if where and spoil:
                out.append(f"SPOILER QUOTE (only in {', '.join(where[:3])}): {frag.strip()[:110]}")
            elif not where:
                m = SequenceMatcher(None, n, inside, autojunk=False).find_longest_match(0, len(n), 0, len(inside))
                out.append(f"MISS ({m.size / max(1, len(n)):.0%} longest run): {frag.strip()[:110]}")
    return out


def later_words(md: str, book: Book, scope: list[int]) -> list[str]:
    seen = set().union(*(book.vocab[i] for i in scope))
    others = [i for i in range(len(book.units)) if i not in scope and (book.collection or i > max(scope))]
    body = re.sub(r"<[^>]+>", " ", "\n".join(md.splitlines()[len(meta(md)):]))
    flagged = {}
    for w in WORD.findall(body):
        k = key(w)
        if k in book.lowered or k not in book.midcaps or k in seen or k.removesuffix("s") in seen or k in flagged:
            continue  # only proper nouns (never lowercase, capitalised mid-sentence) the scope hasn't used
        first = next((i for i in others if k in book.vocab[i]), None)
        if first is not None:
            flagged[k] = book.units[first]["slug"]
    return [f"LATER WORD: {k} (first in {s})" for k, s in sorted(flagged.items(), key=lambda kv: (kv[1], kv[0]))]


def locators(md: str, book: Book, role: str, idx: int | None) -> list[str]:
    out = []
    for pat, what in [(r"\bpp?\.\s*\d", "page number"), (r"\bpara(?:graph)?\.?\s+\d", "paragraph number"),
                      (r"https?://|\]\(", "link")]:
        out += [f"LOCATOR ({what}): …{md[max(0, m.start() - 30):m.end() + 20]!r}…" for m in re.finditer(pat, md)]
    if role in ("unit", "intro"):
        limit = 1 if role == "intro" else (book.units[idx].get("number") or 0)
        for m in re.finditer(r"\b(?:chapters?|ch\.)\s+(\d+)", md, re.I):
            if int(m.group(1)) > limit:
                out.append(f"LOCATOR (chapter beyond the scope): {m.group(0)!r}")
    return out


TITLES = {"mr", "mrs", "miss", "sir", "lady", "the", "and", "dr", "old", "young"}


def digest_cast(md: str) -> list[str]:
    """Names in a digest's "## Cast so far": '- **Name**: …' lines and the 'Also: a, b' line."""
    sec = md.split("## Cast so far", 1)[-1].split("\n## ", 1)[0] if "## Cast so far" in md else ""
    names = re.findall(r"^- \*\*(.+?)\*\*", sec, re.M)
    for line in re.findall(r"^\**Also:?\**:?\s*(.+)$", sec, re.M):
        names += [n for n in re.split(r",\s*|\s+and\s+", line.rstrip(".")) if n.strip()]
    return [re.sub(r"\s*\(.*?\)", "", n).strip() for n in names]


def check_cast(md: str, book: Book, idx: int) -> list[str]:
    prev = book.dir / "companions/.digest" / f"{book.units[idx - 1]['slug']}.cast.md"
    cast = CAST.search(md)
    if not prev.exists() or not cast:
        return []
    have = {key(w) for w in WORD.findall(cast.group(0))}
    return [f"CAST: {n} (cast at the end of {book.units[idx - 1]['slug']}) is missing from Characters so far"
            for n in digest_cast(prev.read_text())
            if not all(key(w) in have for w in WORD.findall(n) if key(w) not in TITLES and len(w) > 2)]


def headings(md: str) -> list[str]:
    return [h.strip() for h in re.findall(r"^(#{1,2} .+)$", md, re.M)]


def target(words: int) -> tuple[int, int]:
    t = min(max(300 + words / 4, 400), 1500)
    return round(t * 0.8), round(t * 1.2)


def check_structure(md: str, book: Book, role: str, idx: int | None) -> list[str]:
    out = []
    if role in ("digest", "digest-cast"):
        want = ["## What happens"] if role == "digest" else ["## Cast so far", "## Threads so far"]
        got = [h for h in headings(md) if h.startswith("## ")]
        if got != want:
            out.append(f"STRUCTURE: digest headings are {got}, want {want}")
        if role == "digest":
            print(f"LENGTH: What happens {prose_words(md)} words, limit 350")
            if prose_words(md) > 350:
                out.append(f"LENGTH: What happens is {prose_words(md)} words, over 350")
        return out
    m = meta(md)
    out += [f"STRUCTURE: missing meta '{k}'" for k in ("title", "eyebrow") if k not in m]
    words_all = prose_words(CAST.sub(" ", "\n".join(md.splitlines()[len(m):])))
    if role == "intro":
        lo, hi = 350, 800
    elif role == "end":
        lo, hi = 1300, 2800
        if '<p class="spoiler">' not in md:
            out.append('STRUCTURE: end.md must open with a <p class="spoiler"> banner')
    else:
        lo, hi = target(book.units[idx]["words"])
        word = "story" if role == "story" else "chapter"
        after = ["# After you read", "## What happened", f"## Characters in this {word}", "## Craft",
                 "## Themes and motifs" + (" so far" if role == "unit" else ""), "## Close reading", "## Questions"]
        before = ["# Before you read", "## Previously", "## Characters so far"] if role == "unit" and idx > 0 else []
        if headings(md) != before + after:
            out.append(f"STRUCTURE: headings are {headings(md)}, want {before + after}")
        if before:
            b = md[md.find("# Before you read"):md.find("# After you read")]
            if '<div class="cast" markdown="1">' not in b:
                out.append('STRUCTURE: Characters so far needs <div class="cast" markdown="1">')
            bw = prose_words(CAST.sub(" ", b))
            print(f"LENGTH: Before you read {bw} words (cast list excluded), limit 275")
            if bw > 275:
                out.append(f"LENGTH: Before you read is {bw} words, over 275")
        if re.search(r"^>.*\n\s*\n>", md, re.M):
            out.append("STRUCTURE: consecutive blockquotes need a <!-- --> line between them")
    print(f"LENGTH: {words_all} words (cast list excluded), target {lo}–{hi}")
    if not lo <= words_all <= hi:
        out.append(f"LENGTH: {words_all} words outside {lo}–{hi}")
    return out


def run(md_path: Path, bookdir: Path) -> list[str]:
    book = Book(bookdir)
    md = md_path.read_text()
    stem = md_path.stem.removesuffix(".cast")
    role, scope, idx = book.scope(stem)
    if md_path.parent.name == ".digest":
        role = "digest-cast" if md_path.stem.endswith(".cast") else "digest"
    spoil = role != "end"
    out = check_quotes(md, book, scope, spoil)
    if spoil:
        out += later_words(md, book, scope)
    out += locators(md, book, role, idx)
    out += check_structure(md, book, role, idx)
    if role == "unit" and idx > 0:
        out += check_cast(md, book, idx)
    return out


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "companions/.text").mkdir(parents=True)
        texts = ["Chapter one. Anna walked to the old mill at dawn and met the miller there.",
                 "Chapter two. The miller told Anna a story about the river and the bridge.",
                 "Chapter three. Then Zebedee arrived with terrible news of the elopement that night."]
        units = [{"nn": f"0{i}", "slug": f"0{i}-chapter-{i}", "kind": "chapter", "number": i, "title": f"Chapter {i}",
                  "words": len(t.split())} for i, t in enumerate(texts, 1)]
        for u, t in zip(units, texts):
            (d / f"companions/.text/{u['slug']}.txt").write_text(t)
        (d / "companions/.units.json").write_text(json.dumps({"form": "novel", "units": units}))
        b = Book(d)
        assert b.scope("02-chapter-2") == ("unit", [0, 1], 1) and b.scope("intro") == ("intro", [0], None)
        md = ("Title: Chapter 2\nEyebrow: Chapter 2\n\n# Before you read\n## Previously\nAnna met the miller.\n"
              "## Characters so far\n<div class=\"cast\" markdown=\"1\">\n- Anna\n</div>\n# After you read\n"
              "## What happened\nThe miller says “told Anna a story about the river”. Zebedee will come; "
              "“arrived with terrible news of the elopement”. Also “the miller sang a song”. See p. 4 and Chapter 3.\n")
        res = run_text(md, "02-chapter-2", d)
        kinds = [r.split(":")[0].split(" (")[0] for r in res]
        assert "SPOILER QUOTE" in kinds and "MISS" in kinds, res
        assert any("zebedee" in r for r in res) and not any(r.startswith("LATER") and "elopement" in r for r in res), res
        assert not any("miller" in r and r.startswith("LATER") for r in res), res
        assert sum(r.startswith("LOCATOR") for r in res) == 2, res
        assert any(r.startswith("STRUCTURE: headings") for r in res), res
        assert not any(r.startswith(("SPOILER", "LATER")) for r in run_text(md, "end", d))
        (d / "companions/.digest").mkdir()
        dg = ("# Chapter 1\n\n## Cast so far\n\n"
              "- **Anna**: walks at dawn.\n- **The miller (unnamed)**: at the mill.\nAlso: Sir Tobias Wren and Old Moll.\n\n"
              "## Threads so far\n\n- Dawn walks.\n")
        (d / "companions/.digest/01-chapter-1.cast.md").write_text(dg)
        (d / "companions/.digest/01-chapter-1.md").write_text("# Chapter 1\n\n## What happens\n\nAnna meets the miller.\n")
        assert digest_cast(dg) == ["Anna", "The miller", "Sir Tobias Wren", "Old Moll"], digest_cast(dg)
        res = run_text(md.replace("- Anna\n", "- Anna, the miller, Tobias Wren\n"), "02-chapter-2", d)
        assert [r for r in res if r.startswith("CAST")] == [
            "CAST: Old Moll (cast at the end of 01-chapter-1) is missing from Characters so far"], res
        for f in ("01-chapter-1.md", "01-chapter-1.cast.md"):
            dres = run(d / "companions/.digest" / f, d)
            assert not any(r.startswith("STRUCTURE") for r in dres), (f, dres)
    print("selftest ok")


def run_text(md: str, stem: str, bookdir: Path) -> list[str]:
    p = bookdir / "companions/src" / f"{stem}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(md)
    return run(p, bookdir)


def main() -> int:
    if sys.argv[1:] == ["--selftest"]:
        selftest()
        return 0
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    out = run(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
    print("\n".join(out))
    print(f"{len(out)} problem(s)")
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main())
