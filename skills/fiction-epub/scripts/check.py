"""Check a built fiction companion EPUB against its source EPUB.

Usage: uv run --quiet --with lxml python -I check.py BOOKDIR OUTDIR

OUTDIR (a scratch folder) receives the unpacked EPUB and screenshots. Prints:
1. per unit: the words of the source slice against the words of NN-text.xhtml (its Notes section
   apart): LOST words are text the EPUB dropped; ADDED words came from fixes or settings. Then each
   carried note against the source note. Then the dropped front and back matter, for the record;
2. links: hrefs to missing files or ids, and noterefs whose note has no link back;
3. epubcheck (W3C), the jar cached in ~/.cache/fiction-epub;
4. screenshots at 412 px (Chromium headless) in OUTDIR/shots: Read them.
Exit 1 if words were lost, links are broken or epubcheck reports errors.
"""
import collections
import json
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from lxml import etree

sys.dont_write_bytecode = True  # no __pycache__ in the dotfiles repo
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "fiction-split/scripts"))
from epubsrc import PARSER, X, Source, etypes, text, words  # noqa: E402

EPUBCHECK = "5.2.1"
CACHE = Path.home() / ".cache/fiction-epub"


def lower(ws):
    return collections.Counter(w.lower() for w in ws)


def show(c: collections.Counter) -> str:
    return " ".join(f"{w}x{n}" if n > 1 else w for w, n in c.most_common(25))


def word_diff(src: Source, m: dict, oebps: Path) -> int:
    print("## 1. words: source EPUB vs built EPUB")
    bad = 0
    for u in m["units"]:
        f = oebps / f"{u['nn']}-text.xhtml"
        body = etree.parse(str(f), PARSER).getroot().find(f"{{{X}}}body")
        notes = [s for s in body.iter(f"{{{X}}}section") if "endnotes" in etypes(s)]
        for s in notes:
            body.remove(s)
        want = [w for b in src.unit_bodies(u) for w in words(text(b))]
        got = words(text(body))
        lost, added = lower(want) - lower(got), lower(got) - lower(want)
        status = "identical" if [w.lower() for w in want] == [w.lower() for w in got] else (
            "same words, different order" if not lost and not added else "DIFFERENT")
        print(f"{u['nn']} {u['title'][:40]}: source {len(want)}, EPUB {len(got)}: {status}")
        if lost:
            print(f"   LOST: {show(lost)}")
            bad += 1
        if added:
            print(f"   added: {show(added)}")
        # carried notes: each noteref's target in the source against the aside with its id
        asides = {a.get("id"): a for s in notes for a in s.iter(f"{{{X}}}aside")}
        for here, b in zip([s["file"] for s in u["src"]], src.unit_bodies(u)):
            for a in b.iter(f"{{{X}}}a"):
                if "noteref" not in etypes(a) and a.get("role") != "doc-noteref":
                    continue
                tf, frag = src.resolve(here, a.get("href", ""))
                target = src.by_id(tf, frag) if frag and src.exists(tf) else None
                if target is None:
                    continue
                if frag not in asides and not body.xpath("//*[@id=$i]", i=frag):
                    print(f"   NOTE MISSING: {frag}")
                    bad += 1
                elif frag in asides:
                    nl = lower(words(text(target))) - lower(words(text(asides[frag])))
                    if nl:
                        print(f"   NOTE {frag} LOST: {show(nl)}")
                        bad += 1
    print("\ndropped as front/back matter:")
    for d in m.get("dropped", []):
        print(f"   {d['file']}: {len(words(text(src.slice(d))))} words ({d.get('why', '')})")
    return bad


def links(oebps: Path) -> int:
    print("\n## 2. links")
    docs = {f.name: etree.parse(str(f), PARSER).getroot() for f in oebps.glob("*.xhtml")}
    ids = {n: {e.get("id") for e in d.iter() if isinstance(e.tag, str) and e.get("id")} for n, d in docs.items()}
    bad = 0
    for name, d in sorted(docs.items()):
        for a in d.iter(f"{{{X}}}a"):
            href = a.get("href")
            if not href or "://" in href or href.startswith("mailto:"):
                continue
            f, _, frag = href.partition("#")
            f = f or name
            if f not in docs and not (oebps / f).exists():
                print(f"{name}: href {href!r}: no file {f}")
                bad += 1
            elif frag and frag not in ids.get(f, set()):
                print(f"{name}: href {href!r}: no id {frag}")
                bad += 1
            elif "noteref" in etypes(a) and frag:
                note = next(e for e in docs[f].iter() if isinstance(e.tag, str) and e.get("id") == frag)
                back = [b for b in note.iter(f"{{{X}}}a") if b.get("href", "").split("#")[-1] == a.get("id")]
                if not a.get("id") or not back:
                    print(f"{name}: noteref to #{frag} has no link back")
                    bad += 1
    refs = sum(1 for d in docs.values() for a in d.iter(f"{{{X}}}a") if "noteref" in etypes(a))
    print(f"{refs} noterefs; {bad} problem(s)")
    return bad


def epubcheck(epub: Path) -> int:
    print("\n## 3. epubcheck")
    jar = CACHE / f"epubcheck-{EPUBCHECK}/epubcheck.jar"
    if not jar.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            z = Path(tmp) / "e.zip"
            urllib.request.urlretrieve(
                f"https://github.com/w3c/epubcheck/releases/download/v{EPUBCHECK}/epubcheck-{EPUBCHECK}.zip", z)
            zipfile.ZipFile(z).extractall(CACHE)
    r = subprocess.run(["java", "-jar", str(jar), str(epub)], capture_output=True, text=True)
    out = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith(("ERROR", "FATAL", "WARNING", "Messages"))]
    print("\n".join(out[:30]) or "(no output)")
    return 0 if r.returncode == 0 else 1


def screenshots(oebps: Path, shots: Path):
    print("\n## 4. screenshots (Read them)")
    shots.mkdir(parents=True, exist_ok=True)
    texts = sorted(oebps.glob("*-text.xhtml"))

    def first(pred):
        return next((f for f in texts if pred(f.read_text())), None)
    pick = [oebps / "intro.xhtml", next(iter(sorted(oebps.glob("*-before.xhtml"))), None), texts[0] if texts else None,
            first(lambda t: "<blockquote" in t), first(lambda t: 'epub:type="endnotes"' in t),
            next(iter(sorted(oebps.glob("*-after.xhtml"))), None), oebps / "end.xhtml", oebps / "nav.xhtml"]
    with tempfile.TemporaryDirectory() as prof:
        for f in dict.fromkeys(p for p in pick if p and p.exists()):
            png = shots / f"{f.stem}.png"
            subprocess.run(["chromium", "--headless", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}",
                            "--window-size=412,900", f"--screenshot={png}", f.as_uri()], capture_output=True)
            print(png)


def main(bookdir: Path, outdir: Path) -> int:
    m = json.loads((bookdir / "companions/.units.json").read_text())
    epub = bookdir / f"{bookdir.name}-companion.epub"
    assert epub.exists(), f"no {epub.name}: run epub.py first"
    zipfile.ZipFile(epub).extractall(outdir / "epub")
    oebps = outdir / "epub/OEBPS"
    src = Source(bookdir / m["source_epub"])
    bad = word_diff(src, m, oebps) + links(oebps) + epubcheck(epub)
    screenshots(oebps, outdir / "shots")
    print(f"\n{bad} failing check(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()))
