#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""Invariants over the BUILT site — docs/architecture.md, "Invariants".

Skips entirely when `site/` has not been generated, so the suite stays green on
a fresh clone. These tests read the output only; they never rebuild it, because
a test that regenerates what it then checks is testing the generator against
itself and will agree with any bug they share.
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from urllib.parse import unquote, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_DIR = os.path.join(ROOT, "site")
sys.path.insert(0, os.path.join(ROOT, "build"))

import inventory  # noqa: E402

HAVE_SITE = os.path.isfile(os.path.join(SITE_DIR, "index.html"))
needs_site = unittest.skipUnless(HAVE_SITE, "site/ not built; run build/generate.py")

# The leading boundary matters: without it this also matches the tail of
# `data-missing-src="…"`, the attribute the generator uses to PARK a link it
# neutralised — so the test would report the generator's own repair as a defect.
LINK = re.compile(r'(?:^|[\s"\'])(?:href|src)\s*=\s*"([^"]*)"', re.I)

WORD = re.compile(r"[\w’'-]+")
CANONICAL_HOST = "fibreculturejournal.org"


def prose_words(text: str) -> list[str]:
    """Words, not tokens.

    `inventory.words` splits on whitespace, which scores Markdown's own
    syntax — `>`, `-`, `#`, `---` — as words and made a faithful render look
    21 words short. Here only the words are counted, on both sides.
    """
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    import html as htmllib
    return [w for w in WORD.findall(htmllib.unescape(text).lower()) if w.strip("-'’")]


def pages() -> list[str]:
    out = []
    for dirpath, _dirs, files in os.walk(SITE_DIR):
        # media/ holds verbatim copies of author-supplied supplementary pages,
        # which still carry their original absolute links. They are preserved
        # as artefacts, not rewritten, so they are not held to these invariants.
        if os.path.relpath(dirpath, SITE_DIR).split(os.sep)[0] == "media":
            continue
        out += [os.path.join(dirpath, f) for f in files if f.endswith(".html")]
    return out


@needs_site
class TestOutputIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = pages()
        cls.docs = {p: inventory.read(p) for p in cls.pages}

    def test_there_is_a_page_for_every_issue_and_paper(self):
        self.assertTrue(os.path.isfile(os.path.join(SITE_DIR, "index.html")))
        self.assertGreaterEqual(len(self.pages), 260)

    def test_no_internal_link_points_at_the_old_hosts(self):
        """Invariant 2, the half that matters most.

        The whole point of the rebuild is that the output does not depend on 33
        hostnames that are about to stop resolving. A surviving absolute link to
        `*.fibreculturejournal.org` is a link that works today on Lightsail and
        breaks the day the archive is actually needed, which is exactly the kind
        of failure that does not show up in a browser test now.

        Two absolute URLs on the APEX host are legitimate and required: the
        `rel="canonical"` link and the Scholar `citation_*` metadata both have
        to be absolute, and the archive is served from that apex. The ban is on
        the 32 issue SUBDOMAINS, which are the hosts that stop resolving.
        """
        canonical = re.compile(r'rel="canonical"')
        offenders = []
        for path, doc in self.docs.items():
            # the canonical <link> is one line; drop it before scanning hrefs
            scanned = "\n".join(ln for ln in doc.splitlines()
                                if not canonical.search(ln))
            for raw in LINK.findall(scanned):
                host = urlsplit(raw).netloc.lower().removeprefix("www.")
                if host.endswith("." + CANONICAL_HOST) or host == CANONICAL_HOST:
                    offenders.append((os.path.relpath(path, SITE_DIR), raw))
        self.assertEqual(offenders[:10], [], f"{len(offenders)} old-host links")

    def test_every_root_relative_link_resolves_in_the_output(self):
        """Invariant 2. A 404 inside the archive is content the reader loses."""
        missing = []
        for path, doc in self.docs.items():
            for raw in LINK.findall(doc):
                # `//host/path` is protocol-relative and therefore external,
                # even though it starts with a slash. One paper cites
                # `//linkchecker.stacken.kth.se/…` that way.
                if not raw.startswith("/") or raw.startswith("//"):
                    continue
                target = unquote(urlsplit(raw).path).lstrip("/")
                candidate = os.path.join(SITE_DIR, target)
                if os.path.isdir(candidate):
                    candidate = os.path.join(candidate, "index.html")
                if not os.path.isfile(candidate) and not os.path.isfile(
                        candidate.rstrip("/")):
                    missing.append((os.path.relpath(path, SITE_DIR), raw))
        self.assertEqual(missing[:10], [], f"{len(missing)} broken internal links")

    def test_no_output_page_carries_the_injected_spam(self):
        """Invariant 1, pending `audit_spam.py`.

        Checked against the injection's own vocabulary rather than the generated
        domain list, which does not exist yet. This is weaker than the invariant
        asks for and is marked as such in docs/IMPLEMENTATION.md. It is still
        worth having: FCJ-129's only copy came from the apex host, where all 145
        contaminated files live, so the archive now draws from the risky source.
        """
        # Matched on the injected DOMAINS, not on vocabulary. A word list
        # produces false positives on the journal's actual subject matter:
        # "cbd" flagged FCJ-056, a paper on cultural planning in Western
        # Sydney, where CBD is the Central Business District. The domains are
        # taken from the measured contamination in fcj-problems.md P3.
        pattern = re.compile(
            r"(instantcasino|onlinecasinomaxi|bestecasinozondercruks|"
            r"safecasinosnotongamstop|sambaslots|bestwallet|exhalewell|"
            r"pokerscout)\.", re.I)
        hits = [os.path.relpath(p, SITE_DIR) for p, d in self.docs.items()
                if pattern.search(d)]
        self.assertEqual(hits, [])

    def test_every_paper_page_keeps_its_source_word_count(self):
        """The theme-extraction risk, measured rather than assumed.

        If the content boundary is wrong for an issue, that issue's papers lose
        text — or gain the site's sidebar, which is what the first build did.
        Comparing output against source catches both directions. The first
        build passed a naive version of this test while publishing 1,702
        identical dead links, so the comparison is on words, not bytes.
        """
        import extract
        import markdown
        # The rendered body only. The template adds a heading, byline, citation
        # line and abstract of its own, none of which are in the Markdown body,
        # so comparing the whole <article> measures the template rather than the
        # fidelity of the render.
        article = re.compile(r'<div class="body">(.*)</div>\s*</article>', re.S)
        content = os.path.join(os.path.dirname(SITE_DIR), "content", "papers")
        if not os.path.isdir(content):
            self.skipTest("content/ not built")
        bad = []
        for path in sorted(os.listdir(content)):
            if not path.endswith(".md"):
                continue
            slug = path[:-3]
            meta, body = extract.parse_front_matter(
                inventory.read(os.path.join(content, path)))
            out = os.path.join(SITE_DIR, "papers", slug, "index.html")
            if not os.path.isfile(out):
                bad.append((slug, "no output page"))
                continue
            # Compare the Markdown against the rendered <article>, which is the
            # only comparison that means anything now: the site is rendered
            # FROM the Markdown, so a mismatch is a renderer bug, and the
            # mirror is no longer involved.
            # Reduce links and images to their visible text. A Markdown link
            # carries its target inline, which a naive word count scores as
            # extra words on the Markdown side only.
            prose = markdown.strip_paragraph_numbers(body)
            prose = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", prose)
            prose = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", prose)
            src_words = len(prose_words(prose))
            m = article.search(inventory.read(out))
            rendered = m.group(1) if m else ""
            # Drop the apparatus the renderer ADDS before counting prose: the
            # paragraph-number rail, note numbers and back-links, and the
            # "Figure N." labels. Counting them made a faithful render look
            # like it had gained 600 words.
            rendered = re.sub(r'(?s)<a class="(?:rail|notenum)".*?</a>', "", rendered)
            rendered = re.sub(r"(?:Figure|Table) \d+\. ", "", rendered)
            out_words = len(prose_words(rendered))
            # Note numbers in the Notes section are stripped above as
            # apparatus, so the Markdown side can legitimately run a few words
            # ahead — one per note. Nothing else should differ at all.
            # A symmetric 1% band with a floor. What this test is for is
            # CONTENT loss or gain — the first build pulled the site's sidebar
            # into every article and lost 69 figure captions, both of which
            # move the count by far more than 1%. Chasing the last few words
            # would mean auditing note numbers and figure labels one by one,
            # which measures the apparatus rather than the prose.
            drift = out_words - src_words
            if src_words and abs(drift) > max(20, src_words * 0.01):
                bad.append((slug, f"{src_words} markdown vs {out_words} output"))
        self.assertEqual(bad[:10], [], f"{len(bad)} papers with drifted word counts")

    def test_the_stylesheet_is_shared_not_per_issue(self):
        """Non-goal in the spec: no per-issue themes. One stylesheet."""
        self.assertTrue(os.path.isfile(os.path.join(SITE_DIR, "assets", "style.css")))
        css = [f for _d, _s, fs in os.walk(SITE_DIR) for f in fs if f.endswith(".css")]
        self.assertEqual(len(css), 1, "exactly one stylesheet")

    def test_fonts_are_self_hosted(self):
        """An archive meant to outlive its own domain must not fetch its
        typography from someone else's CDN at read time."""
        fonts = os.path.join(SITE_DIR, "assets", "fonts")
        self.assertTrue(os.path.isdir(fonts))
        self.assertTrue([f for f in os.listdir(fonts) if f.endswith(".woff2")])
        for path, doc in self.docs.items():
            self.assertNotIn("fonts.googleapis.com", doc, os.path.basename(path))
            self.assertNotIn("cdn.jsdelivr.net", doc, os.path.basename(path))

    def test_every_page_carries_the_issue_index(self):
        """The brief: the list of issues reachable from anywhere."""
        for path, doc in self.docs.items():
            self.assertIn('class="issues"', doc, os.path.relpath(path, SITE_DIR))

    def test_issue_pages_lead_with_their_contents(self):
        """An issue page carries the editorial, but a reader arriving at an
        issue is almost always after an article.

        So the contents comes first and the editorial follows, with the skip
        link pointing PAST the contents to the editorial — the reverse of the
        first version of this page, which made you scroll several thousand
        words of editorial to reach the list of articles.
        """
        for path, doc in self.docs.items():
            if "/issues/" not in path or 'id="contents"' not in doc:
                continue          # an issue with no linked papers has no list
            self.assertIn('href="#editorial"', doc, path)
            self.assertIn('id="editorial"', doc, path)
            self.assertLess(doc.index('id="contents"'), doc.index('id="editorial"'),
                            f"{path}: contents must precede the editorial")

    def test_the_issue_index_names_the_issue_it_points_at(self):
        """A row of bare numbers tells a reader nothing about where they are
        going. The name travels inside the link, so it works on hover, on focus
        and for a screen reader — a `title` tooltip does none of those."""
        for path, doc in self.docs.items():
            self.assertIn('<span class="t">', doc, os.path.relpath(path, SITE_DIR))
            self.assertNotIn('nav class="issues"', doc.replace(
                '<nav class="issues" aria-label="Issues">', ""))

    def test_no_page_leaks_a_markdown_file_link(self):
        """`content/` links files (`fcj-218-….md`, `../media/…`) so the text
        works away from the website. The renderer translates those into site
        URLs, and a missed case ships a page whose links 404."""
        for path, doc in self.docs.items():
            name = os.path.relpath(path, SITE_DIR)
            self.assertNotRegex(doc, r'href="[^"]*\.md[\"#]', name)
            self.assertNotRegex(doc, r'(?:href|src)="\.\./', name)

    def test_no_page_leaks_the_markdown_dialect(self):
        for path, doc in self.docs.items():
            self.assertNotIn("{#para", doc, os.path.relpath(path, SITE_DIR))
            self.assertNotIn("::: embed", doc, os.path.relpath(path, SITE_DIR))

    def test_every_paper_page_carries_scholar_citation_metadata(self):
        """Invariant 7. The archive must be at least as indexable as the site
        it replaces.

        The mirror emitted these tags on 218 of 237 papers. An earlier version
        of the generator dropped them, which would have removed the journal
        from Google Scholar without anything visibly breaking — Scholar accepts
        HTML as full text, but only when the citation tags are present.
        """
        pages = [p for p in self.docs if "/papers/" in p]
        self.assertGreater(len(pages), 200)
        for path in pages:
            doc = self.docs[path]
            name = os.path.relpath(path, SITE_DIR)
            for tag in ("citation_title", "citation_journal_title",
                        "citation_issn", "DC.publisher"):
                self.assertIn(f'name="{tag}"', doc, f"{name} missing {tag}")

    def test_citation_pdf_url_is_only_claimed_when_a_pdf_exists(self):
        """Pointing a harvester at a missing PDF is worse than omitting it."""
        for path, doc in self.docs.items():
            m = re.search(r'name="citation_pdf_url" content="([^"]+)"', doc)
            if not m:
                continue
            local = os.path.join(SITE_DIR, urlsplit(m.group(1)).path.lstrip("/"))
            self.assertTrue(os.path.isfile(local),
                            f"{os.path.relpath(path, SITE_DIR)} claims a missing PDF")

    def test_there_is_a_sitemap_listing_the_whole_corpus(self):
        """A static archive cannot serve OAI-PMH, which takes query
        parameters, so the sitemap is the one machine-readable index of the
        corpus it can offer a harvester."""
        sitemap = os.path.join(SITE_DIR, "sitemap.xml")
        self.assertTrue(os.path.isfile(sitemap))
        xml = inventory.read(sitemap)
        # Every page the site publishes: the front page, the institutional
        # pages, every issue and every paper.
        self.assertEqual(xml.count("<loc>"), len(self.docs))

    def test_the_preservation_indicators_are_on_every_page(self):
        """LOCKSS and the publisher are institutional standing, not decoration.

        The LOCKSS sentence must appear VERBATIM as text: a crawler looks for
        that exact wording, and in the mirror it survived only as the `title`
        attribute of a GIF, where it does nothing.
        """
        statement = ("LOCKSS system has permission to collect, preserve, and "
                     "serve this open access Archival Unit.")
        for path, doc in self.docs.items():
            name = os.path.relpath(path, SITE_DIR)
            self.assertIn(statement, doc, f"{name} lost the LOCKSS statement")
            self.assertIn("Open Humanities Press", doc, f"{name}")
            self.assertIn("ISSN 1449-1443", doc, f"{name}")

    def test_the_institutional_pages_are_published_and_linked(self):
        for slug in ("about", "editorial-and-guidelines",
                     "publication-status"):
            self.assertTrue(
                os.path.isfile(os.path.join(SITE_DIR, slug, "index.html")),
                f"/{slug}/ is not published")
        for path, doc in self.docs.items():
            self.assertIn('nav class="pages"', doc,
                          os.path.relpath(path, SITE_DIR))

    def test_the_editorial_board_reaches_the_site(self):
        """The names are the point of keeping this page at all."""
        page = inventory.read(
            os.path.join(SITE_DIR, "editorial-and-guidelines", "index.html"))
        for name in ("Su Ballard", "Andrew Murphie"):
            self.assertIn(name, page)
        self.assertIn("Editorial Board", page)

    def test_paragraph_citation_numbers_reach_the_pages(self):
        """Was 17,000 when the numbers ran through the notes and references.
        They now stop at the end of the main text, so this measures what is
        actually citable. Bounded on both sides: too few means the apparatus
        cut has eaten into the argument, too many means it stopped working."""
        rails = sum(doc.count('class="rail"') for doc in self.docs.values())
        self.assertGreater(rails, 11_500, "the journal's citation apparatus")
        self.assertLess(rails, 14_500, "apparatus numbering has come back")


@needs_site
class TestTheArchiveSpeaksOnlyWhereItMay(unittest.TestCase):
    """Invariant 8 and its two exceptions.

    The archive puts no text of its own on the journal's pages. Exception (b),
    added 2026-11-27, allows a maintainer contact on the About page so a reader
    who finds a broken link has somewhere to report it — the journal ceased
    publishing in 2019 and its own editorial contact cannot answer for the
    state of the files.

    The exception is only worth having while it stays narrow, so this asserts
    both halves: the contact is on About, and on nothing else. A contact line
    that spread to every page would be the provenance banner the invariant
    exists to forbid.
    """

    MARKER = "archive-contact"

    def _html(self, rel):
        with open(os.path.join(SITE_DIR, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_the_about_page_carries_the_maintainer_contact(self):
        self.assertIn(self.MARKER, self._html(os.path.join("about", "index.html")))

    def test_no_other_page_in_the_site_carries_it(self):
        about = os.path.join("about", "index.html")
        offenders = []
        for dirpath, _dirs, files in os.walk(SITE_DIR):
            for name in files:
                if not name.endswith(".html"):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, name), SITE_DIR)
                if rel != about and self.MARKER in self._html(rel):
                    offenders.append(rel)
        self.assertEqual(offenders, [],
                         "the archive is speaking on pages where it may not")

    def test_the_contact_is_a_contact_and_not_an_explainer(self):
        """8(b) permits a contact line, not a description of the archive."""
        about = self._html(os.path.join("about", "index.html"))
        start = about.index(self.MARKER)
        block = about[start:about.index("</p>", start)].lower()
        self.assertLess(len(block), 300, "the contact line has grown into prose")
        for forbidden in ("preserv", "rescued", "originally published at",
                          "this archive was created"):
            self.assertNotIn(forbidden, block)


if __name__ == "__main__":
    unittest.main()
