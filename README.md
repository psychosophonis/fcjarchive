# The Fibreculture Journal — archive

**Looking for the journal? Read it at [fibreculturejournal.org](https://fibreculturejournal.org/).**
This repository is the archive that site is built from.

*The Fibreculture Journal* (2003–2019, ISSN 1449-1443, Open Humanities Press)
was a peer-reviewed open-access journal of digital media, networks and culture:
237 articles and 31 issues.

## Find a paper

Every article is a Markdown file in [`content/papers/`](content/papers/), named
by its FCJ number — FCJ-218 is `content/papers/fcj-218-….md`. Issue editorials
are in [`content/issues/`](content/issues/), one per issue.

Every article also has a PDF, in one of two places:

- **The journal's own PDF**, for the later issues — the path is on the `pdf:`
  line at the top of the article's Markdown file.
- **An archival offprint** otherwise — the same name in
  [`content/offprints/`](content/offprints/), e.g. `content/offprints/fcj-001.pdf`.

Figures, ePubs and whole-issue PDFs are in [`content/media/`](content/media/).

There is no FCJ-222: the number was reserved for the issue 30 editorial, which
was never written.

## Rebuild the site

If the website ever goes down, it can be rebuilt from this repository alone.
You need Python 3.9 or later and nothing else.

```bash
git clone https://github.com/psychosophonis/fcjarchive
cd fcjarchive
python3 build/generate.py
```

That writes the complete site to `site/`. To look at it locally:

```bash
python3 -m http.server -d site 8000      # then open http://localhost:8000
```

To publish it, copy `site/` to any web host. To keep the journal's old links
working, the host must also apply `site/redirects.map` — every historical URL and
the page it now lives at, one per line.

## Licence

The authors retain copyright in their articles, published under Creative
Commons BY-NC-ND 4.0. The tools are Apache-2.0. See [`LICENCE.md`](LICENCE.md).
