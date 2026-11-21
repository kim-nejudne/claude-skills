"""Check a built companion EPUB.

Usage: uv run --with pymupdf python check.py BOOKDIR OUTDIR

OUTDIR (a scratch folder) receives the unpacked EPUB and screenshots. Prints:
1. per part: words vs companions/.text/<part>.txt (pdftotext of the chapter PDF, notes included):
   the counts, words only in one of them (running heads, chapter titles and folios belong
   only in the PDF text), and short runs changed in place (joins, OCR quirks, fixes);
2. line-break joins whose joined word appears nowhere else unbroken (possible lost compounds:
   add {"compound": "x-y"} fixes for real ones);
3. superscripts left as plain text, stray asterisks, inline-image warnings to fix by hand;
4. epubcheck (W3C), the jar cached in ~/.cache/companion-epub;
5. screenshots at 412 px of a companion, a text opening, a notes page and each page with a
   figure, in OUTDIR/shots: Read them.
"""
import collections
import difflib
import html
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import pymupdf

EPUBCHECK = "5.2.1"
CACHE = Path.home() / ".cache/companion-epub"


def words(s: str) -> list[str]:
    return re.findall(r"[A-Za-z]+", s)


def text_of(path: Path) -> str:
    if not path.exists():
        return ""
    body = re.sub(r"(?s).*?<body>", "", path.read_text(), count=1)  # not the <title>
    return html.unescape(re.sub(r"<[^>]+>", " ", body))


def word_diff(bookdir: Path, oebps: Path, parts):
    print("## 1. words vs pdftotext of the chapter PDF")
    for part in parts:
        nn, stem = part["file"][:2], Path(part["file"]).stem
        raw_path = bookdir / "companions/.text" / f"{stem}.txt"
        if not raw_path.exists():
            print(f"{nn}: no {raw_path.name}, skipped")
            continue
        a = words(re.sub(r"[-\u00ad]\n\s*", "", raw_path.read_text()))
        b = words(text_of(oebps / f"{nn}-text.xhtml") + text_of(oebps / f"{nn}-notes.xhtml"))
        print(f"\n{nn} {part['title'][:50]}: {len(b)} words, pdftotext {len(a)} ({100 * (len(b) - len(a)) / max(1, len(a)):+.1f}%)")
        ca, cb = collections.Counter(w.lower() for w in a), collections.Counter(w.lower() for w in b)
        # order-free, so notes moved from page feet to the chapter's end cost nothing
        print("   only in PDF text: " + " ".join(f"{w}x{n}" for w, n in (ca - cb).most_common(20)))
        print("   only in EPUB:     " + " ".join(f"{w}x{n}" for w, n in (cb - ca).most_common(20)))
        local = collections.Counter()
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            x, y = " ".join(a[i1:i2]), " ".join(b[j1:j2])
            if op == "replace" and i2 - i1 <= 3 and j2 - j1 <= 3 and x.replace(" ", "").lower() != y.replace(" ", "").lower():
                local[f"{y!r} (PDF {x!r})"] += 1
        if local:
            print("   changed in place: " + "; ".join(f"{k}" + (f" x{n}" if n > 1 else "") for k, n in local.most_common(20)))


def join_suspects(doc, parts, fixes):
    print("\n## 2. line-break joins never seen unbroken (real compounds need a {\"compound\"} fix)")
    lines = []
    for p in parts:
        for rng in (p["body"], p.get("notes")):
            for pno in range(rng[0], rng[1] + 1) if rng else ():
                for b in doc[pno - 1].get_text("dict")["blocks"]:
                    for l in b.get("lines", []):
                        lines.append("".join(s["text"] for s in l["spans"]).rstrip())
    whole, hyph = collections.Counter(), set()
    for t in lines:
        body = t.rstrip("-­")
        whole.update(w.lower() for w in words(body))
        hyph |= {w.lower() for w in re.findall(r"[A-Za-z]+-[A-Za-z]+", body)}
    known = {fx["compound"].lower() for fx in fixes if "compound" in fx}
    flag = set()
    for t, n in zip(lines, lines[1:]):
        if t.endswith(("-", "­")):
            a = re.findall(r"[A-Za-z]+$", t[:-1])
            b = re.findall(r"^\s*([a-z]+)", n)
            if a and b and not whole[(a[0] + b[0]).lower()] and f"{a[0]}-{b[0]}".lower() not in hyph | known:
                flag.add(f"{a[0]}-{b[0]}")
    print(f"{len(flag)} joined without hyphen: " + " ".join(sorted(flag, key=str.lower)))


def leftovers(oebps: Path):
    print("\n## 3. leftovers in the text files")
    for f in sorted(oebps.glob("*-text.xhtml")):
        t = f.read_text()
        sups = collections.Counter(re.findall(r'(?<!">)<sup>([^<]*)</sup>', t))
        stars = len(re.findall(r'(?<!">)\*', t))
        if sups or stars:
            print(f"{f.name}: unlinked superscripts {dict(sups.most_common(12))}" + (f"; {stars} plain '*'" if stars else ""))


def epubcheck(epub: Path):
    print("\n## 4. epubcheck")
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


def screenshots(oebps: Path, shots: Path):
    print("\n## 5. screenshots (Read them)")
    shots.mkdir(parents=True, exist_ok=True)
    pick = [next(iter(sorted(oebps.glob(g))), None) for g in ("*-companion.xhtml", "*-text.xhtml", "*-notes.xhtml")]
    pick += [f for f in sorted(oebps.glob("*.xhtml")) if "<figure" in f.read_text()]
    with tempfile.TemporaryDirectory() as prof:
        for f in dict.fromkeys(p for p in pick if p):
            png = shots / f"{f.stem}.png"
            subprocess.run(["chromium", "--headless", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}",
                            "--window-size=412,900", f"--screenshot={png}", f.as_uri()], capture_output=True)
            print(png)


def main(bookdir: Path, outdir: Path):
    manifest = json.loads((bookdir / "chapters/.parts.json").read_text())
    epub = bookdir / f"{bookdir.name}-companion.epub"
    assert epub.exists(), f"no {epub.name}: run epub.py first"
    fixes_path = bookdir / "companions/epub-fixes.json"
    fixes = json.loads(fixes_path.read_text()) if fixes_path.exists() else []
    oebps = outdir / "epub/OEBPS"
    zipfile.ZipFile(epub).extractall(outdir / "epub")
    word_diff(bookdir, oebps, manifest["parts"])
    join_suspects(pymupdf.open(bookdir / manifest["source_pdf"]), manifest["parts"], fixes)
    leftovers(oebps)
    epubcheck(epub)
    screenshots(oebps, outdir / "shots")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
