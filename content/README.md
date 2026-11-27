# The Fibreculture Journal — text archive

237 articles and 31 issue editorials from
*The Fibreculture Journal* (ISSN 1449-1443), a peer-reviewed open-access journal
of digital media, networks and culture published since 2003.

Every article is one Markdown file with YAML front matter. Figures, PDFs and
ePubs are under `media/`. There is no build step and no database: the text is
flat files, and the website in this repository is generated from exactly these
files, so what you read here is what the site shows.

## Layout

```
papers/<fcj-id>-<slug>.md     one article
issues/<n>.md                 one issue editorial, listing its articles
media/…                       figures, article PDFs and ePubs, full-issue PDFs
```

## Front matter

```yaml
fcj_id: FCJ-218
title: "Train Ticket Sharing: Alternative Forms of Computing in the City"
authors:
  - Paula Bialski
issue: 29
published: 2017-06-29
abstract: "…"
source_url: https://twentynine.fibreculturejournal.org/fcj-218-…/
```

`source_url` is the article's original address, so a citation to the published
version can still be checked against it.

## Paragraph numbers

The journal numbers paragraphs, and those numbers are citable — "(Rossiter
2003, para. 76)". They are preserved as a `{#para76}` suffix on each
paragraph, 12,461 of them across the archive. They cannot
be derived from position: the numbering skips captions and some blocks, so only
90 of 237 articles number every paragraph.

To read the text without them:

```bash
sed -E 's/ *\{#para[0-9]+\}//g' papers/fcj-218-*.md
```

## Licence

Articles remain the copyright of their authors, published under Creative
Commons BY-NC-ND. This archive adds no new claim over them.
