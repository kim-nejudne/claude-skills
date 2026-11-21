"""Build one EPUB 3 that wraps each chapter of a novel (or story) in its reading companion.

Usage:
    uv run --quiet --with lxml --with markdown python -I epub.py BOOKDIR
    uv run --quiet --with lxml --with markdown python -I epub.py --selftest

Reads BOOKDIR/companions/.units.json (from /fiction-split), the source EPUB it names, and
BOOKDIR/companions/src/{intro,<slug>,end}.md (from /fiction-companion). Spine:
    intro · for each unit: Before you read, the chapter text, After you read · end essay
The chapter text is the source EPUB's own XHTML for the unit (italics, letters, verse, ids kept),
with the publisher's CSS, fonts and inline styles dropped. Notes the text links to in a dropped
endnotes file are carried to the end of the chapter's file and linked both ways. A unit without a
companion is included as text alone, with a warning. Writes BOOKDIR/<BOOKDIR name>-companion.epub.

Per-book files in BOOKDIR/companions/ (never edit this script):
    epub-settings.json  {"drop_xpath": ["//x:span[@class='ornament']"], "css": "extra rules"}
                        (prefixes: x = XHTML, epub = OPS)
    epub-fixes.json     [{"file": "05-text.xhtml", "find": "...", "replace": "..."}]
                        exact text of the generated file; must match exactly once
"""
import copy
import datetime
import html
import json
import posixpath
import re
import sys
import uuid
import zipfile
from pathlib import Path

import markdown
from lxml import etree

sys.dont_write_bytecode = True  # no __pycache__ in the dotfiles repo
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "fiction-split/scripts"))
from epubsrc import EPUB_TYPE, OPS, X, Source, etypes  # noqa: E402

NS = {"x": X, "epub": OPS}
DEFAULTS = {"drop_xpath": [], "css": ""}
XML_ENTITIES = {"amp", "lt", "gt", "quot", "apos"}
NOTE_TYPES = {"endnote", "footnote", "rearnote", "note"}
MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
         ".svg": "image/svg+xml", ".webp": "image/webp"}
CSS = """\
@namespace epub "http://www.idpf.org/2007/ops";
.eyebrow { font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.05em; }
blockquote { margin: 0.5em 1.5em; }
figure { margin: 1em 0; text-align: center; }
figure img, img { max-width: 100%; }
a.noteref, a[epub|type~="noteref"] { text-decoration: none; padding: 0 0.15em; }
.note, aside[epub|type~="endnote"] { margin-bottom: 1em; }
.src { font-size: 0.85em; font-style: italic; }
.cast p { margin: 0.6em 0 0.2em; }
.cast ul { margin-top: 0; }
.new { font-size: 0.7em; text-transform: uppercase; letter-spacing: 0.05em; border: 1px solid; padding: 0 0.25em; }
.spoiler { font-weight: bold; border: 1px solid; padding: 0.5em; }
blockquote header, blockquote footer { margin: 0.5em 0; }
hr { border: none; text-align: center; margin: 1.5em 0; }
hr::after { content: "* * *"; }
"""


def warn(msg: str):
    print(f"  ! {msg}", file=sys.stderr)


def xml_safe(s: str) -> str:
    """Named HTML entities are not XML: turn them into characters."""
    return re.sub(r"&([a-zA-Z][a-zA-Z0-9]*);",
                  lambda m: m.group(0) if m.group(1) in XML_ENTITIES else html.unescape(m.group(0)), s)


def page(title: str, body: str, lang: str, prefix: str | None, body_type: str | None = None) -> str:
    pre = f' epub:prefix="{html.escape(prefix)}"' if prefix else ""
    bt = f' epub:type="{body_type}"' if body_type else ""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang}" lang="{lang}"{pre}>
<head><meta charset="utf-8"/><title>{html.escape(title)}</title><link rel="stylesheet" href="style.css"/></head>
<body{bt}>
{body}
</body>
</html>
"""


# ---------- companions ----------

def md_to_xhtml(text: str) -> str:
    md = markdown.Markdown(extensions=["extra", "sane_lists"], output_format="xhtml")
    return xml_safe(md.convert(text))


def companion(path: Path) -> tuple[dict, str | None, str]:
    """-> (meta, before-you-read xhtml or None, after-you-read (or whole) xhtml)."""
    lines = path.read_text().splitlines()
    meta, k = {}, 0
    while k < len(lines) and lines[k].strip() and re.match(r"^[A-Za-z]+:", lines[k]):
        key, _, v = lines[k].partition(":")
        meta[key.strip().lower()] = v.strip()
        k += 1
    if "title" not in meta:
        sys.exit(f"{path.name}: missing meta 'Title'")
    body = "\n".join(lines[k:])
    eyebrow = f'<p class="eyebrow">{html.escape(meta.get("eyebrow", "Reading companion"))}</p>\n'
    cut = re.search(r"^# After you read\s*$", body, re.M)
    if re.search(r"^# Before you read\s*$", body, re.M) and cut:
        return meta, eyebrow + md_to_xhtml(body[:cut.start()]), eyebrow + md_to_xhtml(body[cut.start():])
    if cut:
        return meta, None, eyebrow + md_to_xhtml(body)
    return meta, None, eyebrow + f"<h1>{html.escape(meta['title'])}</h1>\n" + md_to_xhtml(body)


# ---------- chapter text ----------

class Text:
    """The chapter files: source slices, their ids, links and notes."""

    def __init__(self, src: Source, units: list, cfg: dict):
        self.src, self.cfg = src, cfg
        self.files = {}    # out name -> [(source file, body copy)]
        self.ids = {}      # (source file, id) -> out name
        self.first = {}    # source file -> out name of its first slice
        self.images = {}   # zip path -> out name
        for u in units:
            out = f"{u['nn']}-text.xhtml"
            self.files[out] = []
            for s in u["src"]:
                body = src.slice(s)
                self.clean(body)
                for el in body.iter():
                    if isinstance(el.tag, str) and el.get("id"):
                        self.ids.setdefault((s["file"], el.get("id")), out)
                self.first.setdefault(s["file"], out)
                self.files[out].append((s["file"], body))

    def clean(self, body):
        for expr in self.cfg["drop_xpath"]:
            for el in body.xpath(expr, namespaces=NS):
                drop(el)
        for el in list(body.iter()):
            if not isinstance(el.tag, str):
                continue
            if el.tag in (f"{{{X}}}style", f"{{{X}}}script", f"{{{X}}}link"):
                drop(el)
                continue
            el.attrib.pop("style", None)

    def is_note(self, a, target) -> bool:
        if "noteref" in etypes(a) or a.get("role") == "doc-noteref":
            return True
        for el in [target, *target.iterancestors()]:
            if etypes(el) & NOTE_TYPES or (el.get("role") or "") in ("doc-endnote", "doc-footnote"):
                return True
        return False

    def link(self, a, here_src: str, out: str, notes: dict, queue: list):
        href = a.get("href")
        if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I):
            return  # external
        tf, frag = self.src.resolve(here_src, href)
        if frag and (tf, frag) in self.ids:
            dest = self.ids[(tf, frag)]
            a.set("href", ("" if dest == out else dest) + f"#{frag}")
            return
        if not frag and tf in self.first:
            a.set("href", self.first[tf])
            return
        target = self.src.by_id(tf, frag) if frag and self.src.exists(tf) else None
        if target is not None and self.is_note(a, target):
            if not a.get("id"):
                a.set("id", f"ref-{frag}")
            if (tf, frag) not in notes:
                notes[(tf, frag)] = (target, a.get("id"), "".join(a.itertext()).strip() or "*")
                queue.append((tf, frag))
            a.set("href", f"#{frag}")
            return
        warn(f"{out}: link {href!r} leads outside the book's units: unlinked")
        unwrap(a)

    def note_aside(self, tf: str, frag: str, target, ref_id: str, label: str, out: str, notes, queue):
        aside = copy.deepcopy(target)
        aside.tail = None
        aside.tag = f"{{{X}}}aside"
        for k in list(aside.attrib):
            del aside.attrib[k]
        aside.set("id", frag)
        aside.set(EPUB_TYPE, "endnote")
        self.clean(aside)
        for a in list(aside.iter(f"{{{X}}}a")):
            if not a.get("href"):
                continue
            t, f = self.src.resolve(tf, a.get("href"))
            if f == ref_id:
                a.set("href", f"#{ref_id}")  # the note's own backlink
            else:
                self.link(a, tf, out, notes, queue)
        back = etree.Element(f"{{{X}}}a", href=f"#{ref_id}")
        back.text = f"{label}."
        first = next((c for c in aside if isinstance(c.tag, str) and c.tag == f"{{{X}}}p"), None)
        host = first if first is not None else aside
        back.tail = " " + (host.text or "")
        host.text = None
        host.insert(0, back)
        return aside

    def image(self, el, here_src: str, attr: str):
        tf, _ = self.src.resolve(here_src, el.get(attr))
        zpath = posixpath.normpath(posixpath.join(self.src.base, tf))
        if zpath not in self.images:
            name = posixpath.basename(tf)
            taken = set(self.images.values())
            stem, ext = posixpath.splitext(name)
            n = 1
            while f"images/{name}" in taken:
                n += 1
                name = f"{stem}-{n}{ext}"
            self.images[zpath] = f"images/{name}"
        el.set(attr, self.images[zpath])

    def render(self, out: str, lang: str, prefix: str | None, title: str) -> str:
        notes, queue = {}, []
        root = etree.fromstring(page(title, "", lang, prefix, "bodymatter").encode())
        body = root.find(f"{{{X}}}body")
        body.text = "\n"
        for here, piece in self.files[out]:
            for a in list(piece.iter(f"{{{X}}}a")):
                if a.get("href"):
                    self.link(a, here, out, notes, queue)
            for img in list(piece.iter(f"{{{X}}}img")):
                if img.get("src"):
                    self.image(img, here, "src")
            for kid in list(piece):
                body.append(kid)
        if notes:
            sec = etree.SubElement(body, f"{{{X}}}section")
            sec.set(EPUB_TYPE, "endnotes")
            sec.set("role", "doc-endnotes")
            h = etree.SubElement(sec, f"{{{X}}}h2")
            h.text = "Notes"
            done = set()
            while queue:  # notes may link to further notes
                key = queue.pop(0)
                if key in done:
                    continue
                done.add(key)
                target, ref_id, label = notes[key]
                sec.append(self.note_aside(*key, target, ref_id, label, out, notes, queue))
        return etree.tostring(root, encoding="unicode", doctype="<!DOCTYPE html>").replace(
            "<!DOCTYPE html>", '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>', 1)


def drop(el):
    """Remove el but keep its tail text."""
    parent = el.getparent()
    if parent is None:
        return
    prev = el.getprevious()
    if el.tail:
        if prev is not None:
            prev.tail = (prev.tail or "") + el.tail
        else:
            parent.text = (parent.text or "") + el.tail
    parent.remove(el)


def unwrap(el):
    """Replace el by its content."""
    parent, prev, i = el.getparent(), el.getprevious(), el.getparent().index(el)

    def put(text, after):
        if text and after is None:
            parent.text = (parent.text or "") + text
        elif text:
            after.tail = (after.tail or "") + text
    put(el.text, prev)
    kids = list(el)
    for k, c in enumerate(kids):
        parent.insert(i + k, c)
    put(el.tail, kids[-1] if kids else prev)
    parent.remove(el)


# ---------- assemble ----------

def main(bookdir: Path):
    manifest = json.loads((bookdir / "companions/.units.json").read_text())
    out_path = bookdir / f"{bookdir.name}-companion.epub"
    if manifest["source_epub"] == out_path.name:
        sys.exit("the source EPUB has the output's name")
    src = Source(bookdir / manifest["source_epub"])
    srcdir = bookdir / "companions/src"
    settings = bookdir / "companions/epub-settings.json"
    cfg = DEFAULTS | (json.loads(settings.read_text()) if settings.exists() else {})
    unknown = set(cfg) - set(DEFAULTS)
    assert not unknown, f"unknown settings: {unknown}"
    fixes_path = bookdir / "companions/epub-fixes.json"
    fixes = json.loads(fixes_path.read_text()) if fixes_path.exists() else []
    units = manifest["units"]
    first_src = units[0]["src"][0]["file"]
    prefix = src.doc(first_src).get(f"{{{OPS}}}prefix")
    lang = src.doc(first_src).get("{http://www.w3.org/XML/1998/namespace}lang") or src.lang

    known = {"intro", "end"} | {u["slug"] for u in units}
    for md in sorted(srcdir.glob("*.md")):
        if md.stem not in known:
            warn(f"{md.name} matches no unit: not included")

    text = Text(src, units, cfg)
    files, spine, nav = {}, [], []

    def add(name, content):
        files[name] = content
        spine.append(name)

    if (srcdir / "intro.md").exists():
        meta, _, body = companion(srcdir / "intro.md")
        add("intro.xhtml", page(meta["title"], body, lang, None))
        nav.append((None, meta["title"], "intro.xhtml", []))
    else:
        warn("no intro.md")
    missing = []
    for u in units:
        nn = u["nn"]
        md = srcdir / f"{u['slug']}.md"
        items = []
        if md.exists():
            meta, before, after = companion(md)
            if before:
                add(f"{nn}-before.xhtml", page(f"{u['title']}: before you read", before, lang, None))
                items.append(("Before you read", f"{nn}-before.xhtml"))
        else:
            missing.append(nn)
            after = None
        add(f"{nn}-text.xhtml", text.render(f"{nn}-text.xhtml", lang, prefix, u["title"]))
        items.append(("Chapter text" if u["kind"] != "story" else "Story text", f"{nn}-text.xhtml"))
        if after:
            add(f"{nn}-after.xhtml", page(f"{u['title']}: after you read", after, lang, None))
            items.append(("After you read", f"{nn}-after.xhtml"))
        nav.append((u.get("part"), u["title"], items[0][1], items if len(items) > 1 else []))
    if missing:
        warn(f"no companion for {len(missing)} unit(s): {', '.join(missing)}: text only")
    if (srcdir / "end.md").exists():
        meta, _, body = companion(srcdir / "end.md")
        add("end.xhtml", page(meta["title"], body, lang, None))
        nav.append((None, f"{meta['title']} (spoilers)", "end.xhtml", []))
    else:
        warn("no end.md")

    for fx in fixes:
        name = fx["file"]
        assert name in files, f"fix names unknown file {name}"
        count = files[name].count(fx["find"])
        assert count == 1, f"fix for {name} matches {count} times: {fx['find'][:60]!r}"
        files[name] = files[name].replace(fx["find"], fx["replace"])
    for name, content in files.items():
        try:
            etree.fromstring(content.encode(), etree.XMLParser(resolve_entities=False, no_network=True))
        except etree.XMLSyntaxError as e:
            sys.exit(f"{name}: not well-formed XML: {e}")

    def li(label, href, kids=()):
        inner = "".join(li(*k) for k in kids)
        return f'<li><a href="{href}">{html.escape(label)}</a>' + (f"<ol>{inner}</ol>" if inner else "") + "</li>"
    toc, k = [], 0
    while k < len(nav):  # consecutive units in the same part nest under it
        part = nav[k][0]
        if part:
            group = []
            while k < len(nav) and nav[k][0] == part:
                group.append(nav[k])
                k += 1
            toc.append(li(part, group[0][2], [(t, h, kids) for _, t, h, kids in group]))
        else:
            _, t, h, kids = nav[k]
            toc.append(li(t, h, kids))
            k += 1
    files["nav.xhtml"] = page("Contents", f'<nav epub:type="toc" id="toc"><h1>Contents</h1><ol>{"".join(toc)}</ol></nav>',
                              lang, None)

    images = {}
    for zpath, name in text.images.items():
        images[name] = src.z.read(zpath)
    book_title = f"{manifest['title']} — with reading companions"
    uid = uuid.uuid5(uuid.NAMESPACE_URL, f"fiction-companion:{manifest['title']}:{manifest['author']}")
    modified = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    man = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
           '<item id="css" href="style.css" media-type="text/css"/>']
    man += [f'<item id="x{n[:-6]}" href="{n}" media-type="application/xhtml+xml"/>' for n in spine]
    man += [f'<item id="img{i}" href="{n}" media-type="{MEDIA.get(posixpath.splitext(n)[1].lower(), "image/png")}"/>'
            for i, n in enumerate(images)]
    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid" xml:lang="{lang}">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="uid">urn:uuid:{uid}</dc:identifier>
<dc:title>{html.escape(book_title)}</dc:title>
<dc:creator>{html.escape(manifest['author'])}</dc:creator>
<dc:language>{lang}</dc:language>
<meta property="dcterms:modified">{modified}</meta>
</metadata>
<manifest>
{chr(10).join(man)}
</manifest>
<spine>
{chr(10).join(f'<itemref idref="x{n[:-6]}"/>' for n in spine)}
</spine>
</package>
"""
    container = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>
"""
    with zipfile.ZipFile(out_path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", CSS + cfg["css"], compress_type=zipfile.ZIP_DEFLATED)
        for name, content in files.items():
            z.writestr(f"OEBPS/{name}", content, compress_type=zipfile.ZIP_DEFLATED)
        for name, data in images.items():
            z.writestr(f"OEBPS/{name}", data, compress_type=zipfile.ZIP_STORED)
    print(f"{out_path}: {len(spine)} spine files, {len(images)} images, {sum(1 for n in files if n.endswith('-text.xhtml'))} chapter texts")


def selftest():
    """Synthetic book: two chapters in one file, one chapter over two files, endnotes in a dropped
    file (one with a backlink, one without), an image, a link to another chapter and an outside
    link. Builds it, then runs check.py's word, note and link checks and epubcheck on the result."""
    import tempfile
    from epubsrc import make_epub
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import check
    png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                        "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")
    with tempfile.TemporaryDirectory() as d:
        book = Path(d) / "test-book"
        (book / "companions/src").mkdir(parents=True)
        make_epub(book / "source.epub", {
            "text/a.xhtml": '<section id="c1"><h2>One</h2><p>Alpha <i>beta</i><a epub:type="noteref" id="r1" '
                            'href="notes.xhtml#n1">1</a> gamma.</p></section><section id="c2"><h2>Two</h2>'
                            '<p style="color:red">Delta.</p><img src="../img/x.png" alt="x"/></section>',
            "text/b1.xhtml": '<h2>Three</h2><p>Epsilon <a href="a.xhtml#c1">see one</a> and '
                             '<a href="colophon.xhtml">colophon</a>.</p>',
            "text/b2.xhtml": '<blockquote><p>Zeta<a epub:type="noteref" href="notes.xhtml#n2">2</a>.</p></blockquote>',
            "text/notes.xhtml": '<ol><li id="n1" epub:type="endnote"><p>First note. <a href="a.xhtml#r1" '
                                'epub:type="backlink">back</a></p></li><li id="n2" epub:type="endnote"><p>Second '
                                'note.</p></li></ol>',
            "text/colophon.xhtml": "<p>Set in type.</p>"}, {"img/x.png": png})
        units = [{"nn": "01", "slug": "01-one", "kind": "chapter", "number": 1, "title": "Chapter 1", "part": "Part I",
                  "src": [{"file": "text/a.xhtml", "from": None, "to": "c2"}]},
                 {"nn": "02", "slug": "02-two", "kind": "chapter", "number": 2, "title": "Chapter 2", "part": "Part I",
                  "src": [{"file": "text/a.xhtml", "from": "c2", "to": None}]},
                 {"nn": "03", "slug": "03-three", "kind": "chapter", "number": 3, "title": "Chapter 3", "part": None,
                  "src": [{"file": "text/b1.xhtml", "from": None, "to": None},
                          {"file": "text/b2.xhtml", "from": None, "to": None}]}]
        (book / "companions/.units.json").write_text(json.dumps({
            "title": "T", "author": "A", "form": "novel", "source_epub": "source.epub", "units": units,
            "dropped": [{"file": "text/notes.xhtml", "why": "notes"}, {"file": "text/colophon.xhtml", "why": "colophon"}]}))
        src_md = book / "companions/src"
        (src_md / "intro.md").write_text("Title: Introduction\nEyebrow: Before you begin\n\n## The premise\n\nText.\n")
        (src_md / "02-two.md").write_text("Title: Chapter 2\nEyebrow: Chapter 2\n\n# Before you read\n\n## Previously\n\n"
                                          "Alpha.\n\n## Characters so far\n\n<div class=\"cast\" markdown=\"1\">\n- **A**: b\n"
                                          "</div>\n\n# After you read\n\n## What happened\n\nDelta.\n")
        (src_md / "end.md").write_text('Title: After the end\nEyebrow: Whole book\n\n<p class="spoiler">Spoilers.</p>\n')
        main(book)
        out = Path(d) / "out"
        zipfile.ZipFile(book / "test-book-companion.epub").extractall(out)
        oebps = out / "OEBPS"
        names = sorted(p.name for p in oebps.glob("*.xhtml"))
        assert names == ["01-text.xhtml", "02-after.xhtml", "02-before.xhtml", "02-text.xhtml", "03-text.xhtml",
                         "end.xhtml", "intro.xhtml", "nav.xhtml"], names
        t1, t3 = (oebps / "01-text.xhtml").read_text(), (oebps / "03-text.xhtml").read_text()
        assert 'href="#n1"' in t1 and 'id="n1"' in t1 and t1.count('href="#r1"') == 2, t1
        assert 'href="#n2"' in t3 and 'href="#ref-n2"' in t3 and 'href="01-text.xhtml#c1"' in t3, t3
        assert "colophon.xhtml" not in t3 and "style=" not in (oebps / "02-text.xhtml").read_text()
        assert (oebps / "images/x.png").exists()
        nav = (oebps / "nav.xhtml").read_text()
        assert nav.index("Part I") < nav.index("Chapter 1") < nav.index("Before you read") < nav.index("Chapter 3"), nav
        src = Source(book / "source.epub")
        m = json.loads((book / "companions/.units.json").read_text())
        assert check.word_diff(src, m, oebps) == 0
        assert check.links(oebps) == 0
        assert check.epubcheck(book / "test-book-companion.epub") == 0
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
    elif len(sys.argv) != 2:
        sys.exit(__doc__)
    else:
        main(Path(sys.argv[1]).resolve())
