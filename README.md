# claude-skills

My [Claude Code](https://claude.com/claude-code) skills, with the scripts that run them unattended.
They are written for my machine (Arch Linux, paths under `/home/kim`) and my habits, so expect to
adapt them rather than use them as they are.

## Skills

Every skill except `karpathy-guidelines` runs only when you type it (`/name …`); none triggers on
its own.

**Nonfiction books (PDF)**
- `split-book`: splits a book PDF into one PDF per chapter, with each chapter's endnotes, and
  writes a manifest the other two reuse.
- `reading-companion`: writes a study companion PDF per chapter (context, argument map, close
  reading, glossary, who's who, quotations), with a separate subagent fact-checking each one.
- `companion-epub`: builds one phone-friendly EPUB that puts each companion before its chapter's
  reflowed text.

**Fiction (EPUB)**
- `fiction-split`: finds a novel's or story collection's chapters in the EPUB and drops front and
  back matter.
- `fiction-companion`: writes a spoiler-safe, text-only companion for each chapter: Before you
  read, then After you read. The companion for chapter N uses only chapters 1..N, enforced by
  per-chapter digests and a separate spoiler checker. The book gets a spoiler-free intro and a
  full-spoiler end essay.
- `fiction-epub`: builds one EPUB holding, for each chapter, Before you read, the source EPUB's own
  chapter XHTML, then After you read. It is checked with a word diff against the source,
  epubcheck and screenshots.

**Apps**
- `bootstrap-autopilot`: turns an app spec into a repo with a roadmap, deploy kit and an
  unattended build loop. Deploys go to a droplet or Vercel, or there is no deploy at all.

**General**
- `karpathy-guidelines`: coding guidelines against common LLM mistakes. It is vendored from
  [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills), MIT
  (see its `LICENSE`).

## Autopilots (`bin/`)

`reading-autopilot` and `fiction-autopilot` run a whole book unattended:
```
fiction-autopilot <book.epub | book folder>   # starts its own tmux session
fiction-autopilot attach
```
- **Stages:** split, then companions, then EPUB, one headless `claude -p` session per stage.
- **Safety:** each run has a 4 GB memory cap and keeps the machine awake.
- **Usage limits:** it waits for the limit to reset, and pauses at 90% of the 7-day limit.
- **Retries:** each stage gets 3 tries; any permission denial stops the run.
- **Resumable:** run it again and it picks up where it stopped.

## Install

```
git clone git@github.com:kim-nejudne/claude-skills.git ~/Documents/claude-skills
~/Documents/claude-skills/install.sh           # links skills/* to ~/.claude/skills, bin/* to ~/.local/bin
~/Documents/claude-skills/install.sh --check   # report missing or wrong links
```
A real file or folder already at a target is moved aside to `<target>.pre-install`, never deleted.

**Tools used:** `uv` (each script fetches its own Python packages), `python3`, `poppler`
(`pdftotext`, `pdftoppm`), `java` (for epubcheck, downloaded on first use), `chromium`
(screenshots), `jq`, `tmux` and `notify-send`.

**Environment** (bootstrap-autopilot, droplet deploys only), e.g. in a shell file that isn't
committed:
```
export BOOTSTRAP_DROPLET_IP=…   # the server apps deploy to
export BOOTSTRAP_DOMAIN=…       # apps live at <app>.$BOOTSTRAP_DOMAIN
```

## Tests

```
tests/fiction-autopilot.sh                                       # fake claude, ~30 s
skills/bootstrap-autopilot/tests/run.sh                          # fake claude and gh, ~2 min
uv run --quiet --with lxml python -I skills/fiction-split/scripts/epubsrc.py --selftest
python3 -I skills/fiction-companion/scripts/check.py --selftest
uv run --quiet --with lxml --with markdown python -I skills/fiction-epub/scripts/epub.py --selftest
python3 -I skills/reading-companion/scripts/check.py --selftest
```
