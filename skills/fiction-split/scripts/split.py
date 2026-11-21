"""Check a fiction manifest against its EPUB, write each unit's plain text, and report coverage.

Usage: uv run --quiet --with lxml python -I split.py BOOKDIR

Reads BOOKDIR/companions/.units.json (written by the agent), writes
BOOKDIR/companions/.text/<slug>.txt per unit (paragraphs separated by blank lines), fills each
unit's "words" and saves the manifest. Coverage: every spine file's words must be accounted for
by units plus "dropped" entries, with nothing counted twice. Exit 1 on any problem.
"""
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ in the dotfiles repo
sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script's folder off sys.path
from epubsrc import Source, text, words  # noqa: E402

KINDS = {"prologue", "chapter", "interlude", "epilogue", "story"}


def main(bookdir: Path) -> int:
    mpath = bookdir / "companions/.units.json"
    m = json.loads(mpath.read_text())
    src = Source(bookdir / m["source_epub"])
    problems = []
    if m.get("form") not in ("novel", "collection"):
        problems.append(f"form must be novel or collection, not {m.get('form')!r}")
    units = m["units"]
    width = len(units[0]["nn"]) if units else 2
    seen, last = set(), -1
    textdir = bookdir / "companions/.text"
    textdir.mkdir(parents=True, exist_ok=True)
    covered = {}  # spine file -> words assigned
    for u in units:
        nn, slug = u["nn"], u["slug"]
        if nn in seen or len(nn) != width or not nn.isdigit():
            problems.append(f"{nn}: nn must be unique, {width} digits")
        seen.add(nn)
        if not re.fullmatch(rf"{nn}-[a-z0-9]+(-[a-z0-9]+)*", slug):
            problems.append(f"{nn}: slug {slug!r} must be '{nn}-' + lowercase words joined by '-'")
        if u.get("kind") not in KINDS:
            problems.append(f"{nn}: kind {u.get('kind')!r} not in {sorted(KINDS)}")
        if m.get("form") == "collection" and u.get("kind") != "story":
            problems.append(f"{nn}: a collection's units are stories")
        paras = []
        for s in u["src"]:
            if s["file"] not in src.spine:
                problems.append(f"{nn}: {s['file']} is not in the spine")
                continue
            if src.spine.index(s["file"]) < last:
                problems.append(f"{nn}: {s['file']} comes before the previous unit's file in the spine")
            last = src.spine.index(s["file"])
            try:
                t = text(src.slice(s))
            except ValueError as e:
                problems.append(f"{nn}: {e}")
                continue
            covered[s["file"]] = covered.get(s["file"], 0) + len(words(t))
            paras.append(t)
        body = "\n\n".join(p for p in paras if p)
        if not words(body):
            problems.append(f"{nn}: empty text")
        (textdir / f"{slug}.txt").write_text(body + "\n")
        u["words"] = len(words(body))
    dropped = {}
    for d in m.get("dropped", []):
        try:
            n = len(words(text(src.slice(d))))
        except (ValueError, KeyError) as e:
            problems.append(f"dropped {d.get('file')}: {e}")
            continue
        dropped[d["file"]] = dropped.get(d["file"], 0) + n
        if d["file"] not in src.spine:
            problems.append(f"dropped {d['file']} is not in the spine")
    stale = sorted(p.name for p in textdir.glob("*.txt") if p.stem not in {u["slug"] for u in units})
    if stale:
        problems.append(f"stale text files (delete them): {stale}")
    mpath.write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n")

    print("== UNITS (nn | words | part | title | src)")
    for u in units:
        where = ", ".join(s["file"] + (f"#{s['from']}" if s.get("from") else "") + (f"..#{s['to']}" if s.get("to") else "")
                          for s in u["src"])
        print(f"{u['nn']} | {u['words']:>6} | {u.get('part') or '-'} | {u['title']} | {where}")
    print("\n== COVERAGE (spine file | words | in units | dropped)")
    for f in src.spine:
        total = len(words(text(src.body(f)))) if src.body(f) is not None else 0
        a, b = covered.get(f, 0), dropped.get(f, 0)
        flag = ""
        if f not in covered and f not in dropped:
            flag = "  <- UNASSIGNED" if total else ""
            if total:
                problems.append(f"{f}: {total} words in no unit and not dropped")
        elif a + b != total:
            flag = "  <- GAP" if a + b < total else "  <- OVERLAP"
            problems.append(f"{f}: {total} words, units {a} + dropped {b}")
        print(f"{f} | {total} | {a} | {b}{flag}")
    print(f"\nunits {len(units)}, unit words {sum(u['words'] for u in units)}, dropped words {sum(dropped.values())}")
    print("\n".join(f"PROBLEM: {p}" for p in problems) or "no problems")
    return 1 if problems else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(Path(sys.argv[1]).resolve()))
