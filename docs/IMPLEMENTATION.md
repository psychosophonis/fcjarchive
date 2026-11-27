# Implementation status

A human-maintained scratchpad. The real source of truth is the test suite;
this file is just a quick map of where things stand.

```
python3 -m unittest discover -s tests -p 'test_*.py'
```

Build and view:

```
python3 build/extract.py       # mirror + recovered/ -> content/  (~5s, run once)
python3 build/redirects.py     # crawl + mirror -> redirect map  (~30s, run once)
python3 build/audit_spam.py    # mirror -> data/spam-domains.txt  (~3s, run once)
python3 build/audit_content.py # content/ -> a report of furniture residue
python3 build/pdfs.py          # content/ -> content/offprints/  (needs an engine)
python3 build/generate.py      # content/ -> site/               (~1s, every edit)
python3 -m http.server -d site 8000
```

`build/recover.py` is run deliberately and separately: it is the only tool
that touches the network, and the only writer of `recovered/`. Every other
step works offline.

## State at last session close — 16 November 2026

Verify passes: **240 tests, OK**, with `check-docs.sh` clean.

Every stage above has been run, in that order, and the recovery is complete as
far as the Internet Archive allows: **83 of the 85 off-domain files are in
`recovered/`**, every one with its snapshot timestamp and sha256 in
`recovered/MANIFEST.tsv`, and re-running `recover.py` fetches nothing. No
figure in the archive is still remote; `audit_content.py` reports 60 hits, 0 in
enforced categories.

**Nothing is committed to git.** `git log` says the branch has no commits, and
the index holds a stale partial `git add` from an earlier session: of 1,124
paths, 52 are staged-then-deleted and 10 are untracked. The next session should
reset the index and make one initial commit of the whole tree rather than trust
that snapshot. `content/` and `recovered/` are deliberately NOT ignored — they
are the archive, not build output; `site/` is.

Two decisions are **waiting on Mat**, and no code should move on either until he
answers, because both are editorial rather than technical: the 13 old-domain
`.html` citations (item 2 below) and the offprint provenance text (item 9).

## What the archive contains

| | |
|---|---|
| Papers | 237, of which 227 of the 228 numbered articles |
| Issues | 31 editorials, all from the mirror |
| Authors | 235 of 237 from citation metadata |
| Abstracts | 109 lifted into front matter |
| Paragraph numbers | 12,461 preserved as `{#paraN}` — the main text only; 5,335 that ran on into notes, references and biographies are stripped |
| Media | 707 files, 437 MB, hardlinked into `site/` — 83 of them recovered from the Wayback Machine |
| Redirects | 1,766 exact rules + 33 host fallbacks, 0 unmapped |
| Institutional pages | 3 — About, Editorial Board/Policy/Guidelines, publication status |
| Offprints | 126 generated PDFs, for papers with no publisher PDF |
| Pages | 274 |

## Working

- `build/resolve.py` — URL path on an archived host to a file in the mirror.
- `build/inventory.py` — the manifest, plus `data/known-absent.txt`.
- `build/markdown.py` — HTML to the Markdown dialect and back.
- `build/extract.py` — writes `content/`.
- `build/redirects.py` — every crawled URL that served an article maps.
- `build/audit_spam.py` — discovers 78 injected domains by evidence.
- `build/audit_content.py` — reports platform residue in `content/`; never
  rewrites. It exists because five defects in one session were found by Mat
  reading pages, which does not scale to 274 of them.
- `build/recover.py` — the only tool that touches the network, and the only
  writer of `recovered/`. Refuses non-media content types and truncated
  snapshots, and writes the manifest after every fetch, so an interrupted run
  keeps its provenance.
- `build/pdfs.py` — offprints; converts correctly, cannot render without an engine.
- `build/generate.py` — renders `site/` from `content/` alone.
- `assets/style.css`, `assets/offprint.typ` — the design, hand-edited.

**All seven spec invariants are now satisfied** except the part of 4 that
concerns mesh (permitted `absent`), and invariant 1 is enforced over both
`content/` and `site/`.

## Known incomplete, in priority order

1. **Two off-domain files cannot be recovered.** This was 68 figures in 9 early
   papers, pointing at `journal.fibreculture.org`, the journal's pre-2008
   domain, which the crawl never entered and which now returns 503. They were
   never deliberately dropped: the WordPress migration imported some images per
   page and left others as hand-written absolute URLs to the old host, which
   worked until that host died. `recover.py` has been run and 83 of the 85
   referenced files are in `recovered/`. What the Internet Archive does not
   hold:

   - `issue10/roundtable/roundtable.mov` — no snapshot.
   - `issue7/issue7_BtMW_FC_visualization.pdf` — the snapshot is **truncated at
     source**, 130,710 of 2,280,778 bytes. Refused rather than written out: 6%
     of a PDF is not the PDF, and a file that claims to be a document and will
     not open is worse than the gap it fills. The report says so in those
     terms, because a bare "failed" invites a pointless retry.
2. **13 old-domain URLs are citations, not assets.** `issue1/issue1_barnet.html`
   and the like are references to the journal's own pre-2008 articles, which
   are IN this archive. 11 of 13 map by issue plus surname; `stockwellmuir`
   (two authors) and `kucklich` (an umlaut) do not. **Not fixed, because it is
   an editorial decision**: these sit inside authors' reference lists, so
   pointing them at the archive's own copies alters what an author wrote.
3. **Nothing serves the redirect map.** `redirects.json` exists and every target
   is verified to exist, but a JSON file is not a redirect. It needs a
   CloudFront Function with a KeyValueStore (1,766 rules is past the inline
   limit), or a Caddy/nginx map. A deployment decision, not code.
4. ~~**`ARCHIVE_REPO` is unset**~~ — resolved 2026-11-27: set to
   https://github.com/psychosophonis/fcjarchive, so every page footer links
   back to the Markdown archive.
5. **198 domains on 61 apex-only pages are untestable** by the twin-diff, since
   those pages have no clean copy. None are published; see fcj-problems.md P3.
6. **Transitive supplementary material.** 14 of FCJ-062's 53 dynmed files are
   adopted; files linked from *those* pages are not followed.
7. **FCJ-203 and FCJ-212 have no recorded authors** — no citation metadata in
   the mirror. FCJ-212 is issue 29's editorial. They are skipped for offprints
   rather than bylined "Anonymous".
8. **Banners are on by default.** Only 13 of 31 issues have their own; the
   rest share one generic strip, which is not an identity and is not
   extracted. Still undecided whether the 13 should show at all.
9. **The offprint provenance text is unresolved — waiting on Mat.** He asked
   that nothing be added to the journal, and the colophon page, masthead notes
   and corrections record were all removed accordingly. The provenance block in
   the 126 generated offprints was kept and flagged instead of removed, on the
   grounds that it is what stops a generated PDF passing as the publisher's
   version of record. Three parts, to be decided separately: the journal's own
   data line, the warning that the pagination is not the publisher's, and the
   archive's narration of itself. The build date is **already gone** — it baked
   into every file, so a no-op rebuild rewrote all 126, and that was a defect
   regardless of the decision.

## Direction — archiving, not journal management

Mat's aim is a persistent, robust archiving and publishing system; on his view
it supersedes OJS for that purpose, because peer review workflow "is largely
window dressing and most of that happens in the background as journal
management".

That reorders priorities, and it is worth writing down because it decides what
NOT to build. The product is durability, portability and citability: flat
Markdown in git, citation metadata, redirect coverage, offprints, byte-level
fidelity. Submission portals, reviewer assignment and role management are out of
scope — they happen out of band.

And the shape matters as much as the scope. Those capabilities **hang off the
git structure as separate tools** — a suite, not one architecture. See
"The repository is the integration point, not an application" in
`architecture.md`, which is normative.

The current build already has this shape, which is the point: `extract`,
`redirects`, `audit_spam`, `pdfs` and `generate` are five independent programs
communicating through files. Deleting `pdfs.py` costs the offprints and nothing
else. Anything added later takes the same form.

What would move this from archive to publishing system, as separate tools:

| tool | what it would do | already possible because |
|---|---|---|
| issue assembly | take papers in the same front-matter format and write `issues/<n>.md` | the format is specified and `generate.py` reads it blindly |
| DOI registration | read front matter, deposit to Crossref, write the DOI back | `doi` is already a front-matter key, and derived files never get one |
| submission | open a pull request adding a `papers/*.md` | git is the transport; nothing else needs to know |

None is blocked by the current design. None should start before the archive is
live — the remaining gap there is deployment, not code.

## Notes — the things that are easy to get wrong

- **Inputs are read-only.** `fcj-static/`, `fcj-crawl/`, `fcj-kit/`. Invariant 6.
- **`generate.py` must never read the mirror.** That boundary is what stops the
  published text and the published site disagreeing.
- **Identity is the FCJ number from the `<title>` citation, not the slug**, and
  only the `<title>` is searched: a bibliography cites other papers by number.
- **Redirects key on identity, not on the resolved file.** The mirror holds a
  paper at up to three paths and publishes one; a file-keyed map missed 247
  article URLs, including all 214 rules in `fcj-redirects.conf`.
- **Attribution never comes from a slug.** `nineteen…/issue-1-ubiquity` is issue
  19's editorial under a slug reading as issue 1.
- **Paragraph numbers cannot be derived from position**, and come in two markup
  variants. `proofs/markdown-fidelity.py` records the failed first claim.
- **Div balance cannot bound a content region**, and nor can `<table.*?</table>`
  bound a table: FCJ-101 nests a table in a table. Both need balanced scans.
- **Paragraphs are often unclosed**, so terminate on the next block element.
- **`wp-content` is not furniture** — it holds `dynmed`, `pdfs`, `ePubs` too.
- **Images come from the content region; PDFs and ePubs do not.**
- **Every image needs its own block**, or its caption survives only as `alt`.
- **A block can mix list items and plain lines** — keeping only the `- ` lines
  dropped 141 words of references in nine papers.
- **A spam blocklist needs a guard that reads TEXT, not just links.** `chcf.org`
  was flagged because the author cited it as plain text. A false positive makes
  the archive forbid a real source.
- **Pandoc re-reading its own grid tables is quadratic.** Convert a table to
  typst once and splice it as a raw block; the alternative hung a test run.
- **Pink is interaction, mono is apparatus.** The two rules the design rests on.
- **The seven 503 holds should become 301s** on the live site, and the redirect
  map already resolves them. fcj-problems.md P1.
- Measured findings and open questions live in `fcj-problems.md`, not here.
