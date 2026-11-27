# The Fibreculture Journal — archive

A static archive of the original WordPress powered *The Fibreculture Journal*, a
peer-reviewed open-access journal of digital media, networks and culture
published since 2003. Articles remain the copyright of their authors under
Creative Commons BY-NC-ND.

That site ran well for over a decade but exposed issues of archiving, resilience
and sustainability. This system was designed to answer that and to provide a
secure archive. It is increasingly being developed as a more resilient journal
system.

**237 articles · 31 issue editorials · every FCJ number that was published.**

## What is here

```
content/            THE ARCHIVE — this is the thing worth keeping
  papers/*.md         one article per file, front matter + text
  issues/*.md         one issue editorial per file
  media/              figures, publisher PDFs and ePubs, whole-issue compilations
  offprints/          generated PDFs for articles the journal never published one for
  redirects.json      every historical URL -> its path here
build/              the tools, five independent programs
docs/               the specification, and what is built against it
data/               generated evidence: injected spam domains, absent articles
assets/             the site's design, and the offprint template
tests/              186 tests
site/               generated; not committed
```

`content/` needs nothing else to be useful. Every article is plain Markdown with
YAML front matter, every link inside it is relative, and the figures sit beside
the text — so a clone, a single downloaded file, or a GitHub file view all work
without this website existing.

## Build it

Requires Python 3.9+ (standard library only), and for the offprints
[pandoc](https://pandoc.org) with [typst](https://typst.app).

```bash
python3 build/extract.py      # crawled mirror -> content/     (~4s, run once)
python3 build/redirects.py    # crawl + mirror -> redirect map (~30s, run once)
python3 build/audit_spam.py   # mirror -> data/spam-domains.txt (~3s, run once)
python3 build/pdfs.py         # content/ -> content/offprints/
python3 build/generate.py     # content/ -> site/              (~1s, every edit)
python3 -m http.server -d site 8000
```

The first three read the crawled mirror and are the one-way, lossy stage.
`generate.py` reads **only** `content/`, which is the boundary the whole design
rests on: the text published here is the text the website shows, so the two
cannot drift, and no amount of restyling can damage a word of it.

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

## How it is put together

Each capability is a separate program that reads and writes files. There is no
database, no application server and no runtime — git is the transport, the audit
log and the backup. Any tool can be run, re-run or deleted without the others
noticing; deleting `build/pdfs.py` costs the offprints and nothing else. The
front matter, the Markdown dialect and the directory layout are the interface
they integrate through, and they are specified in
[`docs/architecture.md`](docs/architecture.md) rather than left to whatever the
code happens to emit.

The failure mode this avoids is the one that put the journal here: a
database-backed application that the entire scholarly record lives inside, and
that nobody can upgrade. The failure mode of a repository of flat files is a
dead link.

## Reading the text

Paragraph numbers are preserved as a `{#para76}` suffix, 17,800 of them, because
the journal numbers paragraphs and people cite them — "(Rossiter 2003, para.
76)". They cannot be derived from position: only 90 of 237 articles number every
paragraph. To read without them:

```bash
sed -E 's/ *\{#para[0-9]+\}//g' content/papers/fcj-218-*.md
```

## Known gaps

Recorded rather than hidden; see [`docs/fcj-problems.md`](docs/fcj-problems.md) and
[`docs/IMPLEMENTATION.md`](docs/IMPLEMENTATION.md).

- **There is no FCJ-222.** The number was reserved for the issue 30
  editorial, which was never written; `data/known-absent.txt` records the
  evidence.
- **82 internal links** point at supplementary material the crawl never
  captured. They keep their text and record where they pointed, rather than
  being silently dropped.
- The site is not yet deployed, and nothing serves `redirects.json` yet.

## Licence

The authors retain copyright in their articles, published under Creative
Commons BY-NC-ND 4.0. This archive claims nothing over them. The tools and the
design are Apache-2.0 — free to use and change, with the attribution kept
attached; the vendored fonts carry their own licence. See
[`LICENCE.md`](LICENCE.md).
