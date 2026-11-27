# Architecture specification

This is a NORMATIVE document: the implementation MUST match what is written
here. Update it BEFORE you change behaviour, then make the code follow.

## Purpose

Build a clean, self-contained static archive of The Fibreculture Journal — all
papers, all issue editorials, and their images, PDFs and ePubs — from the crawled
WordPress mirror. The output is one host with root-relative links, so it serves
identically from a local directory, from S3+CloudFront, and from a GitHub Pages
style host, and can be iterated on locally with no DNS, TLS or privileges.

Measured facts this spec is derived from are recorded in
`fcj-problems.md` ("Inventory baseline"). Where this spec states a number,
that file is the evidence.

## Inputs (all read-only; the build MUST NOT modify them)

Every input lives in `source/`, beside this repository, within the project
root:

```
<project root>/
  fcjarchive/     this repository — the product
  source/         the inputs below; read-only, never on the render path
  deploy-old-crawl/  the setup that served the crawled mirror — NOT for
                  this archive: its Caddyfile redirects the apex out to the
                  33 subdomains, the opposite of what the archive needs
```

The build MUST locate them through `resolve.SOURCE_ROOT`, which derives that
directory from its own `__file__`, and MUST NOT write out an absolute path. An
absolute path makes relocating the project a code change, and a silent one:
every mirror-dependent test is guarded by `skipUnless(os.path.isdir(...))`, so
a stale path drops 52 of 240 tests while the suite still reports OK.
`tests/test_architecture.py` enforces this.

| input | role |
|---|---|
| `source/fcj-static/` | crawled mirror, 33 hosts, 620 MB, 4,592 files |
| `source/fcj-crawl/fcj-clean.cdx` | crawl index, 3,896 URLs over 33 hosts; the authority for Invariant 5 |
| `source/fcj-kit/fcj2022.sql.gz` | WordPress dump; sole source of the 4 lost editorials |
| `source/fcj-redirects.conf` | canonical redirect source (Apache syntax), 207 × 301 + 7 × 503 |

## The repository is the integration point, not an application

A direction set by Mat, and it governs everything below: the capabilities that
a journal platform like OJS bundles into one system — submission, review, issue
assembly, DOI registration — **hang off the git structure as separate tools**.
They are not built into one architecture.

So:

- **Every capability is its own executable**, reading and writing files in the
  repository. `extract`, `redirects`, `audit_spam`, `pdfs` and `generate` are
  already five independent programs over a file boundary, not five modes of one
  application. Anything added later follows the same shape.
- **Any tool must be removable.** Deleting `pdfs.py` costs the offprints and
  nothing else; `generate.py` does not know it exists. If a new tool cannot be
  deleted without breaking another, it has been built wrong.
- **No shared database, no application server, no runtime.** Git is the
  transport, the audit log and the backup.
- **Therefore the content format is a PUBLIC CONTRACT**, not an internal
  detail. The front matter keys, the Markdown dialect and the directory layout
  are the interface that separate tools integrate through, and they may not be
  changed casually — which is why they are specified here rather than left to
  whatever `extract.py` happens to emit.

The failure mode this avoids is the one that put the journal here: a
database-backed application that the entire scholarly record lives inside, and
that nobody can upgrade. The failure mode of a repository of flat files is a
dead link.

**What this rules out**, concretely, so it is not rediscovered later: adding
editorial workflow features to `generate.py`; a configuration database; any
step that must run before the text is readable; and any coupling that makes two
tools need to be released together.

## Two stages, with a file boundary between them

The build is two stages, and the boundary is the point of the design:

```
extract   mirror HTML  ->  content/     lossy, one-way, runs once, audited
render    content/     ->  site/        cheap, repeatable, reads nothing else
```

`render` MUST NOT read `fcj-static/`. The text in `content/` is therefore the
text the website shows, and the two cannot drift. Restyling the journal cannot
damage a word of it, and design iteration costs about a second.

## Content format — `content/` is the archive

```
content/
  README.md                      how to use the text, and how to strip the markers
  papers/<fcj-id>-<slug>.md      front matter + the article
  issues/<n>.md                  front matter + the issue editorial
  media/<mirror-relative path>   figures, article PDFs/ePubs, full-issue PDFs
```

Front matter is a deliberately small YAML subset — scalars and lists of scalars,
nothing nested — so it parses with the standard library and reads cleanly in a
GitHub file view. Authorship, date and DOI come from the page's own Google
Scholar / Dublin Core citation metadata, not from parsing the prose.

### Front matter — the contract between tools

This is the interface separate tools integrate through, so it is specified
rather than left to whatever `extract.py` emits. A tool MAY add keys; it MUST
NOT repurpose or silently drop these.

**`papers/<fcj-id>-<slug>.md`**

| key | required | meaning |
|---|---|---|
| `fcj_id` | yes | `FCJ-218`. Canonical identity, from the `<title>` citation |
| `title` | yes | article title, without the id |
| `authors` | yes | list. From `citation_author`; for the two numbered editorials whose posts record none (FCJ-203, FCJ-212), declared in `extract.EDITORIAL_AUTHORS` — their issue editors, not the journal's managing editors |
| `affiliation` | — | as printed in the byline |
| `issue` | yes | `1`…`30` or `mesh` |
| `published` | — | ISO date |
| `doi` | — | the PUBLISHED article's DOI. Never one minted for a derived file |
| `abstract` | — | lifted out of the body |
| `pdf`, `epub` | — | publisher's files, as `media/…` paths |
| `pdf_generated` | — | an archival offprint; MUST be distinguishable from `pdf` |
| `source_url` | yes | the article's original address, so a citation can be checked |
| `source_file` | yes | provenance within the mirror |
| `journal`, `issn`, `licence` | yes | constant, but written out so a single file stands alone |

**`issues/<n>.md`**

| key | meaning |
|---|---|
| `issue` | `1`…`30` or `mesh` |
| `theme` | as the issue's own title gives it; may be absent |
| `editorial_source` | `mirror-standalone` \| `mirror-root` \| `dump` \| `absent` |
| `editors` | list of `Name` or `Name, Institution` |
| `doi` | the issue DOI, where the journal registered one |
| `papers` | list of `fcj_id`, in the order the issue presents them |
| `full_issue_pdf`, `full_issue_epub` | whole-issue compilations, as `media/…` paths |
| `banner`, `banner_ratio` | the issue's own header artwork, where it had one |
| `journal`, `issn`, `source_file` | as above |

Issue editors MUST be recovered rather than dropped. The journal credited them
through WordPress metadata inserts which the crawl flattened into prose, in
three different shapes — a `###### Issue Edited by` heading, an
`Introduction by **Name** of Institution` sentence, and bio paragraphs near the
foot of the editorial — and only the second carries institutions. "Edited by"
also occurs inside editorial prose citing other people's books, so a credit is
recognised only as a heading. A role written into the name
(`**Lone Bertelsen***, Issue Editor*`) is stripped from it.

An issue's editorial MUST NOT carry the issue's own hand-written table of
contents: the archive generates that list from the manifest and places it above
the editorial, so keeping the original prints the issue twice.

A file must stand alone: someone who receives one `.md` and nothing else should
be able to cite it correctly. That is why `journal`, `issn` and `licence` are
repeated in every file rather than held once in a config somewhere.

### Paths — two conventions, deliberately

**In the body, links are RELATIVE to the file that uses them**, always with the
directory segment:

```markdown
![caption](../media/eighteen.fibreculturejournal.org/files/2011/09/1_intro.jpg)
[FCJ-218 Train Ticket Sharing](../papers/fcj-218-train-ticket-sharing-….md)
[Issue 29](../issues/29.md)
```

A root-relative `/media/…` resolves on the website and nowhere else: in a
GitHub file view it points at the repository root rather than the file, and a
single `.md` someone downloaded has no images at all. The archive promises text
that can be reused *without* the website, so its links must work without it.
The directory segment is required even for a sibling — writing one as a bare
filename made `issues/19.md` link another issue as `19.md`, which is
indistinguishable from a paper and rendered as a broken `/papers/19/`.

**In front matter, paths are relative to the CONTENT ROOT** (`media/…`,
`offprints/…`). Front matter is data read by tools, not Markdown rendered by a
viewer, and a tool reading it holds the content root rather than the file's
directory. The two conventions sit in one file and would look inconsistent
without this note.

`generate.py` translates body links into site URLs when it renders, which it
can do because it owns every output path. No page in `site/` may contain a
`.md` href or a `../` target.

### The Markdown dialect

The dialect is CLOSED: the only Markdown rendered is the Markdown written by
this project. That is what makes a stdlib-only renderer honest, and it is
proven by round-tripping real papers in `tests/test_markdown.py`.

```
## … ######        section headings; an in-body <h1> demotes to ##
text {#para76}     a paragraph, carrying the journal's citation number
*em*  **strong**   emphasis; `em` carries meaning (work titles), not style
[text](url)        link
![caption](src)    figure; the caption is the alt text (Pandoc's convention)
> quote            blockquote, which may itself hold numbered paragraphs
- item             list item
---                horizontal rule
::: embed / url / :::   an embedded player the archive cannot host
`<tag>`            markup the author QUOTED, as a code span
<table>…</table>   raw HTML, passed through whole
```

**Paragraph numbers MUST be carried, not derived.** The journal numbers
paragraphs and they are cited — "(Rossiter 2003, para. 76)". They are
sequential, but only 90 of 237 papers number every paragraph, so the nth
paragraph is not paragraph n; and 232 papers mark them with `id="paraN"` while
others print `- 76 -` in the paragraph's own text. Both variants MUST be read.
`proofs/markdown-fidelity.py` is the record of this, including the first
version of the claim that was wrong.

**Tables are the one HTML exception**, and are passed through WHOLE, including
any markup inside them: FCJ-101 lays out its argument in a two-column table
whose cells hold 20 numbered paragraphs, which keep their native ids.

## Output layout

```
site/
  index.html                     journal front page, lists all issues
  issues/<n>/index.html          the issue EDITORIAL, then that issue's contents
  papers/<fcj-id>-<slug>/index.html
  media/<mirror-relative path>   hardlinked from content/, never copied
  assets/style.css               the whole design; one stylesheet, no per-issue themes
  assets/fonts/*.woff2           self-hosted, SIL OFL
  redirects.json                 every historical URL -> new path
```

### Presentation requirements

These are requirements, not taste, because the archive is a scholarly record:

1. **Authorship and date** on every article, from citation metadata.
2. **Paragraph numbers** rendered as a clickable margin rail, and as the
   paragraph's `id`, so a citation by paragraph still resolves.
3. **Figures** as `<figure>` with a real `<figcaption>`, numbered where the
   caption does not already carry a label. A caption that exists only as `alt`
   text is a lost caption.
4. **Notes** linked both ways: a `[7]` in the prose to its note, and the note
   back to its reference. Rebuilt from structure, not from the mirror's anchors.
5. **References** with a hanging indent, so surnames align for scanning.
6. **Emphasis preserved** — 12,430 instances, mostly work titles in references.
7. **A print stylesheet**, since no PDFs exist for the early issues: the
   browser's "Print to PDF" must produce a readable offprint, not a screenshot
   of a website.
8. **Self-hosted fonts.** An archive meant to outlive its own domain must not
   fetch its typography from someone else's CDN at read time.

Rule: **the issue root is the editorial.** This was the original design intent of
the subdomains and held for 25 of 31 issues; the archive makes it uniform.

## API Contracts

Module boundaries. Each is a pure function over the filesystem unless stated.

```
resolve.local_path(host, url_path) -> str | None
  Maps a URL path on an archived host to a file in fcj-static.
  MUST handle all five conventions found in the mirror, sometimes mixed
  within one issue:
    1. flat file               one/fcj002.html
    2. extensionless URL       /fcj-001        -> fcj-001.html
    3. directory slug          /fcj-218-slug/  -> .../index.html
    4. dated permalink         /2016/03/21/<slug>/
    5. themed intro slug       /issue-21-affect-in-interaction/
  MUST percent-decode, MUST try NFC and NFD forms (macOS stores either),
  MUST strip trailing whitespace inside href quotes (the mesh theme emits it).
  Returns None rather than guessing.

inventory.build(static_root) -> Manifest
  Drives from each issue root's own links, NOT from slug patterns and NOT from
  the FCJ number sequence; both demonstrably miss content (FCJ-212 is issue 29's
  editorial; issue 2's papers carry no number in their slugs).
  Every unresolved reference MUST appear in Manifest.unresolved, never be
  silently dropped.

editorials.recover(dump_path, issue_no) -> Editorial | None
  Extracts an issue editorial from the WordPress dump. Required for issues
  1, 2, 5 and 23, whose editorials are absent from the mirror.

markdown.to_markdown(content, rewrite_url) -> str
  HTML content region -> the dialect above. MUST carry every paragraph number
  from either markup variant. MUST NOT lose a word of prose.

markdown.render(md) -> str
  The dialect -> HTML meeting the presentation requirements above.

extract.write_content(manifest, out_dir) -> ExtractReport
  Writes `content/`. Lifts authorship, date, DOI and abstract into front
  matter. An internal link it cannot map to an archive path MUST become plain
  text, never a link to a host that is going away.

generate.write_site(out_dir, content_dir) -> Report
  Renders `site/` from `content/` ALONE. MUST NOT read the mirror. Media is
  hardlinked from `content/media`, not copied.

redirects.build(manifest) -> RedirectReport
  Built from the CRAWL INDEX, with fcj-redirects.conf as a second source.
  Never hand-edited, so the map and the archive cannot drift apart.

  MUST key on the article's IDENTITY — the FCJ citation in its <title> — and
  not on the file a URL resolves to. The mirror holds the same article at up to
  three paths (apex copy, issue-subdomain copy, dated permalink) and the
  archive publishes one, so a lookup keyed on the resolved file misses every
  apex duplicate: 247 article URLs, including all 214 of the conf's rules.

  Output is an exact map plus a per-host fallback. The fallback exists because
  2,705 crawled URLs are WordPress furniture — category listings, author pages,
  feeds, date archives, paginated indexes — and 2,705 individual rules saying
  "go to the issue index" would be a worse artefact than one rule per host.

  The seven 503 "held back" rules MUST resolve to the clean issue-subdomain
  copies: the premise of the hold ("spam injected into the only copy") is false,
  and all five articles have clean twins. See fcj-problems.md P1.
```

### redirects.json

Keys are `host + path`: lower-cased host with `www.` stripped, percent-decoded
path, no trailing slash, no query, no fragment. **A consumer MUST normalise an
incoming URL the same way**, which is why the file states the rule in its own
`note` field rather than leaving it to be rediscovered. Lookup order is `exact`,
then `host_fallback` for the request's host, then 404. `redirects.map` is the
same data as tab-separated text for a Caddy/nginx map or a CloudFront
KeyValueStore import, generated in the same call so the two cannot disagree.

```
```

## Data Models

Every page linked from an issue root is classified, and the classification is
part of the model. 213 of the 254 linked pages carry an FCJ number; 41 do not,
and the archive MUST NOT invent an identity for those. Deriving identity from a
slug is the error `proofs/editorial-recovery.py` falsified: `nineteen…/issue-1-ubiquity`
is issue 19's editorial under a slug reading as issue 1.

```
Kind = "paper" | "editorial" | "unclassified"
  paper         an FCJ-\d+ citation in <title>; keyed by that id
  editorial     the issue root, or a page whose body text duplicates it
  unclassified  anything else: carried in the manifest with its source path,
                never dropped, never assigned a guessed identity

Paper {
  fcj_id: str        // "FCJ-218" — canonical identity, taken from the <title>
                     // citation, NOT from the slug. Slugs use five conventions
                     // and change between issues; the citation does not.
  issue: int
  slug: str          // output slug, stable once published
  source: str        // path in fcj-static this was built from
  title: str
  words: int
  images: list[str]
  pdf: str | None
  epub: str | None
}

Issue {
  number: int
  theme: str
  editorial_html: str
  editorial_source: str   // "mirror-root" | "dump" | "absent"
  papers: list[str]       // fcj_ids, in the order the issue root lists them
  full_issue_pdf: str | None
  full_issue_epub: str | None
}

Manifest {
  papers: dict[str, Paper]
  issues: dict[int, Issue]
  assets: dict[str, int]       // output path -> bytes
  unresolved: list[Unresolved] // never silently dropped
  unclassified: list[Page]     // linked, resolved, but not a paper or editorial
}

Accounting invariant: for every issue root, the number of distinct page links it
carries equals papers + editorials + unclassified + unresolved for that issue.
Asserted by `tests/test_inventory.py`. It is the only thing standing between a
report that looks complete and one that is.
```

## Invariants (what the tests assert)

1. **No spam.** No file in `content/` and no page in `site/` links any domain in
   `data/spam-domains.txt`. That file is generated by the audit, never
   hand-maintained.

   A domain is listed only on two conditions together: it appears in an apex
   copy of an article and NOT in that article's clean issue-subdomain twin, AND
   it appears nowhere in the text of any of the 32 issue subdomains. The second
   is the guard, and it must read the TEXT rather than only `href` attributes —
   a paper that cites a URL in plain text would otherwise have that source
   banned. 78 domains across 54 files, measured over 190 article pairs.
2. **No dead internal links.** Every root-relative href and img src in the output
   resolves to a file in `site/`.
3. **Completeness.** Every FCJ number from 001 to 228 is either present or listed
   in `data/known-absent.txt` **with a reason**, and that file is generated by
   `inventory.write_known_absent`, never hand-written. FCJ-222 is the only
   entry. The reason is part of the invariant: a bare list of gaps reads as an
   oversight, and the next reader would otherwise spend a day rediscovering
   that FCJ-222 is not recoverable from anything the archive holds.
4. **Every issue has an editorial**, with `editorial_source` recorded. Issues 1,
   2, 5 and 23 MUST come from the dump; mesh is permitted `absent`.
5. **Redirect coverage.** Every URL the crawl recorded that served an article or
   an editorial maps to an archive path, and every target resolves to a file in
   `site/`. The 214 rules in `fcj-redirects.conf` are a subset that must also
   hold.

   This replaces an earlier, narrower version of this invariant which named
   only `fcj-redirects.conf`. That file's rules redirect apex duplicates to
   issue subdomains — internal plumbing of the old site — and say almost
   nothing about where a historical URL should land in a single-host archive.
   The authority is `fcj-crawl/fcj-clean.cdx`: 3,896 URLs over 33 hosts, every
   one status 200.

7. **Harvestable metadata.** Every article page carries Google Scholar
   (`citation_*`) and Dublin Core metadata, because the archive must be at
   least as indexable as the site it replaces — the mirror emitted these tags
   and losing them would quietly remove the journal from Scholar.
6. **Inputs untouched.** The build MUST NOT write inside `fcj-static/`,
   `fcj-crawl/` or `fcj-kit/`.

   This extends to the second input: `recovered/` is read-only to the build
   too. Only `build/recover.py` writes it, only when run deliberately, and
   `extract.py` MUST NOT import it — so a build stays reproducible offline
   from the mirror plus whatever recovery has already brought back.
8. **No text of the archive's own on the journal's pages.** No editorial
   notes, no provenance banners, no explanation of what the archive is. At the
   editors' instruction, and the right default regardless: an added explainer
   is the archive speaking in the journal's voice. There are exactly two
   exceptions, both narrow and both named here:

   a. The provenance line in a generated offprint, which exists to stop a new
      artifact passing as an original — see "Offprints".

   b. **A contact for whoever maintains the archive**, on the About page only.
      Added at Mat's instruction, 2026-11-27. The reasoning for the invariant
      does not cover it: a reader who finds a broken link or a mis-scanned
      figure needs somewhere to report it, and the journal ceased publishing in
      2019, so its own editorial contact can no longer answer for the state of
      the files. This is the archive being accountable, not the archive
      explaining itself — so it is a contact line and MUST NOT grow into a
      description of what the archive is or why it exists.

      The address lives in `content/journal.md` as `archive_contact`, not in
      code and not in `content/pages/about.md`, which is regenerated. One
      declaration, rendered by `generate.py`.
9. **Paragraph numbers stop at the end of the main text.** They are the
   citable unit; a numbered reference list implies a reference can be cited by
   paragraph.

## Institutional pages and journal metadata

A journal's standing rests on being able to show who edits it, how it reviews,
and who preserves it. An archive of the articles alone silently demotes a
peer-reviewed journal to a pile of PDFs, so these are part of the archive, not
decoration around it.

### `content/pages/*.md`

A page type, not a fixed list of FCJ's pages. Front matter carries `title` and
`nav_order`; the header picks up whatever is there. For FCJ:

| page | from | holds |
|---|---|---|
| `about` | `about` | the journal's scope and purpose |
| `editorial-and-guidelines` | `policy-and-style` | **editorial board, journal editors and manager, editorial policy, submission guidelines, style guide, copyright** |
| `publication-status` | composed | that the journal ceased publishing, with the year from `journal.md` |

The source list MUST be explicit and never a directory scan: the same apex
directory holds `write-for-us-sponsored-posts`, an artefact of the compromise,
alongside several hundred category and date-archive pages.

#### The journal's own downloads

The manifest is built by walking issue roots and papers, so it never saw an
institutional page's attachments — and `make_rewriter` DROPS any internal link
whose target is not in the manifest, keeping the link text and discarding the
anchor. The journal's four procedural documents were therefore published as
plain text with no link at all:

- FCJ Guidelines 2014 (the full principles, guidelines and forms)
- the Referee's Report form
- the Issue Editor Agreement
- the Author Submission Forms

These are the documents the journal's own peer review ran on, and the mirror
holds the only copies. `page_assets()` registers a page's attachments in the
manifest so the rewriter resolves them, and `write_pages` copies them.

#### Normalisation

These pages used bold text as headings, bolded the text *inside* real headings
(`#### **editor**`), set role headings in lower case, and carried an in-page
navigation menu whose anchors no longer exist. All are presentation, not
structure, and all are normalised on extraction — including the heading level,
since a sliced subsection starts at `####` but is now a page in its own right
and is promoted so its shallowest heading is `##`.

The menu needed two rules, not one, because WordPress put its label and its
links in separate `<p>` elements: removing `**Page Navigation:**` left behind

```
:: editorial board and management
:: editorial policy
```

Menu removal is anchored to **line-initial `::` in a leading block**. `::` is
also an authored inline separator in the About page's list of topics, and
`::: embed` is a fence in the Markdown dialect. A rule that simply deleted `::`
would destroy both.

### Theme code vs. the shared asset bucket

`wp-content/themes` holds two unlike things:

| directory | what it is |
|---|---|
| `fcjissue19`, `fcjmain`, `fcjmeshX`, `fcjissue` | code themes; their images are the old site's chrome |
| `fcsharedimg` | a bare asset bucket — 183 files of issue artwork, **including every issue banner** under `banners<N>/` |

**Excluding the whole of `themes` would delete all 13 banners.** That is the
same mistake `FURNITURE` already records for `wp-content/uploads`: a directory
is not a category.

`inventory.in_code_theme()` therefore applies a **structural** test rather than
a list of names — WordPress requires a theme to declare itself in `style.css`,
so a theme directory with one is code and a directory without one is storage.
If a crawl ever missed a theme's `style.css`, this keeps files rather than
dropping them, which is the safe direction to be wrong in.

### Pruning

`content/` is generated, so a file in it the build no longer produces is stale,
and stale is worse than missing: it still renders and still serves. `_prune`
covers `.md` in `papers/` and `issues/`, and every file under `media/` the
build did not copy.

`MEDIA_FLOOR` is **a refusal, not a tuning knob**. Media pruning deletes from
the tree holding every image, PDF and ePub in the archive, driven by a set its
caller assembles. If that set comes back short — a swallowed exception, a
manifest that failed to build, a caller that forgot to pass it — the honest
outcome is to delete nothing and say so, because the mirror is read-only
(invariant 6) and a wrong deletion is recoverable only by a full re-extract.

### Nothing is added to the journal

**The archive publishes no text of its own on the journal's pages.** No
editorial notes, no provenance banners, no explanation of what the archive is.
This is at the editors' explicit instruction, and it is the right default for
an archive: an added explainer is the archive speaking in the journal's voice.

The one exception, which exists to PREVENT a misrepresentation rather than to
add one, is the provenance line in a generated offprint — see "Offprints".

#### Corrections

`extract.CORRECTIONS` is the archive's only departure from the crawled pages.
Everything else is faithful, errors included, because an archive that quietly
improves its source cannot be cited.

A correction MUST carry:

- a **section-level scope**, not a page-level one. "Andrew Murphie" is both the
  journal manager the crawled page names and one of its five journal editors;
  a page-wide replacement would delete him from the editors, substituting one
  false claim for another.
- a **stated reason**, in the declaration itself. The list is the record: the
  archive publishes no corrections notice, because that would be text added to
  the journal.

### `content/journal.md`

Journal-level metadata — title, ISSN, publisher, licence, preservation
statement, contact. The renderer reads the footer, the imprint and the
indicators from here rather than carrying one journal's details in Python
string literals.

**It is seeded once by `extract.py` and then hand-maintained**, and is the only
file in `content/` that is not regenerated. `extract.py` MUST NOT overwrite an
existing one. Adopting this archive for another journal is then: a different
mirror, a different `journal.md`, and your own `pages/`.

### Preservation indicators

**The LOCKSS permission statement MUST appear verbatim, as text, on every
page.** A LOCKSS crawler looks for that exact wording:

> LOCKSS system has permission to collect, preserve, and serve this open access
> Archival Unit.

In the mirror it survived only as the `title` attribute of a GIF, where it does
nothing. The publisher (Open Humanities Press) and the ISSN are shown with it.

**An unresolved conflict, recorded rather than decided:** the mirror's apex
footer carries a **CC BY 4.0** licence badge, while every article and the
journal's own statements say **CC BY-NC-ND**. The archive uses BY-NC-ND and
flags the discrepancy; resolving it is the journal's call, not the archive's.

## Paragraph numbers stop at the end of the main text

The numbers are the journal's **citable unit** — the thing a reader cites
instead of a page, since the archive's pagination is not the published
pagination. They ran on into the notes, references, biographies and
appendices: **5,335 of 17,796 of them, in 217 of 237 papers.** In an offprint
they are set in the margin, so a reference list arrived with a numbered rail
beside it, implying a reference can be cited by paragraph. It cannot.

`extract.unnumber_apparatus()` strips them from the apparatus. The cut is
**the trailing run of apparatus headings**, walking back from the end of the
document, NOT the first apparatus heading:

> Ten papers have an apparatus heading *inside* the article — `Notes` followed
> by `Appendix I`, `Author's Biography` followed by `Journal Note`. Cutting at
> the first match would unnumber the rest of those articles: destroying the
> citable unit for most of a paper in order to tidy up its reference list.

The rule reads a property of the document, never a list of filenames.

One consequence worth knowing: because the cut is a *run*, a single unmatched
heading in the middle of the apparatus stops the walk. `Authors’ Biographies`
with a curly apostrophe failed a pattern written for `Author's` — and that one
miss left `Notes` numbered in ten papers. The heading set is therefore tested
directly, in both directions.

Offprints need no separate rule: `pdfs.py` draws the margin rail from
`{#paraN}` in the Markdown, so removing them at the source fixes the PDFs and
the site together. This is the two-stage boundary paying for itself.

## Recovered files: a second input

**85 references in `content/` point at `journal.fibreculture.org`** — the
journal's pre-2008 domain. It is a *different domain* from
`fibreculturejournal.org`, so it was never in the crawl's scope and nothing
under it is in the mirror.

They were not always missing. The mirror shows the mechanism: on one page in
FCJ-039 a migrated image carries `wp-image-109` while the one beside it still
points off-domain with its hand-written 2005 `width`/`height`. The WordPress
migration imported some images per page and left the rest as absolute URLs to
the old domain. That domain still resolves — to the same failing host this
archive exists to replace — and now returns 503.

### What is recovered and what is not

| refs | kind | treatment |
|---|---|---|
| 81 | `.jpg` | recovered — all but one, which has no snapshot |
| 3 | `.pdf` | recovered — author-supplied supplementary material — all but one, whose snapshot is truncated at source |
| 1 | `.mov` | no snapshot exists |

**82 of the 85 are recovered.** The three that are not:

| file | why |
|---|---|
| `images/Andrews_Figure2small.jpg` | no snapshot |
| `issue10/roundtable/roundtable.mov` | no snapshot |
| `issue7_BtMW_FC_visualization.pdf` | snapshot **truncated at source** — the Internet Archive holds 130,710 of 2,280,778 bytes |
| 13 | `.html` | **NOT recovered.** These are citations to the journal's own pre-2008 articles, and those papers are in this archive. Fetching them would publish a second copy of an article the archive already holds, at a different URL — the duplication this rebuild exists to remove. They need mapping to internal links, which is a separate change and an editorial decision, since rewriting a URL inside an author's reference list alters their citation. |

### `recovered/` and provenance

`build/recover.py` is **the only tool that touches the network and the only
writer of `recovered/`.** `extract.py` must never import it, which
`test_architecture.py` enforces: a build has to be reproducible offline from
the mirror plus `recovered/`.

The tree mirrors the mirror's layout
(`recovered/journal.fibreculture.org/images/melinda1.jpg`) and is committed,
because these bytes exist nowhere else now.

**Provenance is load-bearing, not decorative.** This is the archive's only
content from outside the crawl, so `recovered/MANIFEST.tsv` records per file:
the original URL, the Wayback timestamp the bytes came from, the sha256, the
byte count, and the papers that reference it. A reader can then tell a figure
taken from a 2018 snapshot from one that came off the crawl.

`resolve.recovered_path()` is deliberately SEPARATE from `resolve.local_path()`
rather than a fallback inside it, so a lookup can never silently pass from the
mirror into recovered content. "Did this come off the crawl?" must stay an
answerable question.

Invariant 6 extends rather than bends: `recovered/` is read-only to the build,
exactly as the mirror is.

### Two ways a snapshot lies

**The soft-404.** The Wayback Machine can serve an HTML error page with status
200. Written out as a `.jpg` it would look like a corrupt image forever after,
with nothing to say why. A fetch is accepted only if the response's own
`Content-Type` is an image, PDF, video or audio type — never on the strength
of the extension — and the sha256 is recorded so a bad fetch can be
identified later.

**The truncated capture.** A snapshot can be incomplete while the server still
declares the full length; that is what raised `IncompleteRead` on the one PDF
the Internet Archive holds only 6% of. **6% of a PDF is not the PDF**, so a
short read is refused and reported with its measured shortfall rather than
written out as a document that cannot open. The distinction matters in the
report: "truncated snapshot: 130710 of 2280778 bytes" says what to do next,
where a bare "failed" invites a pointless retry.

### Finding what the rewriter cannot see

`make_rewriter` only sees Markdown link targets. Two shapes common in the
early issues are invisible to it — a raw `<img src="https://…">` inside HTML
this dialect passes through untouched, and a bare URL in running text — and 13
of the recovered files were referenced only that way. `point_at_recovered()`
is a post-pass over the body text that catches them.

It is restricted to MEDIA extensions on purpose. A bare URL in a reference
list is a citation, and rewriting a citation's target to a local path would
corrupt what an author wrote.

## Content audit

Five defects in one session were found by a person reading pages rather than by
the build: `#####` headings on an issue, a dead `::` menu, the old theme's PDF
icons, a run of `Issue:ePubIssue:pdf` labels, and an issue recorded under a
generic title. Each was then fixed with a one-off rule.

**That approach scales with how many pages somebody reads, and there are 275.**
`build/audit_content.py` detects the CLASS instead: WordPress and theme
furniture that survived extraction — text that was interface on the old site
and is meaningless in a Markdown archive.

It REPORTS and never rewrites. Several checks need judgement, and a tool that
rewrote them would damage the thing it protects. Two of its own checks were
wrong when first written, and acting on either would have damaged content:

- `deep-heading` flagged five authored subsections in a paper on falling
  robots. It is furniture on an issue page, where the old theme used heading
  level as a font size, and structure in a paper. Now scoped.
- `empty-link` flagged uncaptioned figures as broken links. `![](src)` is a
  figure whose caption was not found — a real concern, but not a broken link,
  and deleting it would delete the figure. Now a separate, unenforced
  category.

A category is ENFORCED — failing the build — only once every one of its hits
has been read and confirmed to be furniture. Enforcing a noisy check trains
people to ignore the whole report, which is worse than not having it.

Unenforced findings currently standing:

| finding | count | why it is not a build failure |
|---|---|---|
| `remote-image` | 68 figures in 9 early papers | they point at `journal.fibreculture.org`, a domain outside the crawl; **no copy exists in the mirror**, so this cannot be fixed by editing text |
| `uncaptioned-figure` | 27 | some figures genuinely have no caption in the source |
| `bold-as-heading` | 31 | a pull-quote or figure label is legitimately bold |

## Offprints

128 of the 237 papers have no PDF, and 121 of those are in issues 1-16
(2003-2010). An author with a 2005 paper has nothing to deposit in their
institutional repository. `build/pdfs.py` renders one.

**An offprint is made ONLY where no publisher PDF exists.** Where the journal
published its own PDF that file is the version of record, and generating a
second rendering of the same article would put two different-looking documents
of the same paper into circulation. The split is exact and has no overlap:

| | count |
|---|---|
| publisher PDF, used as-is | 109 |
| archival offprint generated | 128 |
| neither | 0 |

A paper with no recorded author gets no offprint: a PDF with no byline is worse
than no PDF for deposit, so those two are reported by name rather than bylined
"Anonymous".

**Every offprint MUST carry a provenance colophon** stating that it was
generated from this archive, that it is not the publisher's version of record,
and that its page numbers are not the published pagination. **No offprint is
given a DOI of its own**; the `doi` it prints is the published article's, so a
reader can reach the version of record. Without this the archive would be
manufacturing a second citable object for one paper.

This is the ONE exception to invariant 8, "no text of the archive's own". It
earns it by preventing a misrepresentation rather than adding an explanation:
these PDFs did not exist before the archive typeset them, and an unmarked
generated offprint is indistinguishable from a publisher PDF.

**It carries no generation date.** The code used to call `date.today()` under a
comment claiming the date was fixed, so every offprint recorded the day it
happened to be built and a no-op rebuild rewrote all 126 — 126 modified
binaries in a repository that commits them, and a real change invisible in the
diff. When a file was typeset is the repository's job to record. `pdfs.py`
therefore imports no clock, which is what the test asserts.

Layout follows the journal's own later PDFs (issues 17-30, produced with
Asciidoctor PDF in 2017), measured from `FCJ-218PaulaBialski.pdf`: A4, single
column, Open Sans, `FCJ-nnn ` before the title, a one-line byline,
`Abstract:` bold inline, a `doi:` line, unnumbered bold headings, references as
a bulleted hanging-indent list, page number in the footer, no running header.

One deliberate departure: those PDFs carry no paragraph numbers, but for issues
1-16 the numbered HTML was the only published form, so citations to those
papers cite paragraphs. The numbers are set in the outer margin, placed outside
the text flow so the body sets identically to an offprint without them.

`generate.py` discovers offprints **by path** — `content/offprints/<slug>.pdf` —
rather than by importing `pdfs.py` or having `pdfs.py` write into another
tool's files, so either can be run, re-run or deleted without the other.

## Non-goals (deliberately excluded for now)

Author pages, tag and category indexes: WordPress-generated, reconstructible
later from `Paper` metadata, and not needed to read the journal. Excluded until
there is a requirement for them.

## Verification

```
python3 -m unittest discover -s tests -p 'test_*.py'
```

Tests that prove this spec holds:

| test | invariant |
|---|---|
| `tests/test_resolve.py` | all five URL conventions, percent-encoding, NFC/NFD, trailing space |
| `tests/test_inventory.py` | unresolved references are reported, never dropped |
| `tests/test_archive_integrity.py` | invariants 1, 2, 3, 5 — skips if `site/` is not built |
| `tests/test_editorials.py` | invariant 4, including the four dump-recovered issues |
