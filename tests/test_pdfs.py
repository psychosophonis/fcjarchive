#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""Tests for build/pdfs.py — docs/architecture.md, "Offprints".

Most of these need no PDF engine: the risk is in the pre-processing and the
metadata, not in the typesetting. The two that need an engine skip with a clear
message rather than passing silently, because "the PDF is complete" is a claim
that must not be assumed.

The provenance test is the one that matters most. For issues 1-16 the HTML is
the version of record; an offprint that does not say so would manufacture a
second citable object for the same paper.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "build"))

import extract  # noqa: E402
import markdown  # noqa: E402
import pdfs  # noqa: E402

CONTENT = os.path.join(ROOT, "content")
HAVE_PANDOC = shutil.which("pandoc") is not None
HAVE_CONTENT = os.path.isdir(os.path.join(CONTENT, "papers"))
ENGINE = pdfs.find_engine()

needs_pandoc = unittest.skipUnless(HAVE_PANDOC, "pandoc not installed")
needs_content = unittest.skipUnless(HAVE_CONTENT, "content/ not built")
needs_engine = unittest.skipUnless(
    ENGINE, "no PDF engine installed — `brew install typst`; PDF completeness "
            "is UNPROVEN until then")


def words(text: str) -> list[str]:
    return [w for w in re.findall(r"[\w’'-]+", text.lower()) if w.strip("-'’")]


class TestPreprocessing(unittest.TestCase):
    """Pure. The dialect must not reach the reader."""

    def test_paragraph_marker_becomes_a_margin_number(self):
        out = pdfs.preprocess("Some text. {#para76}")
        self.assertNotIn("{#para76}", out)
        self.assertIn("#place(left", out)
        self.assertIn("[76]", out)
        self.assertIn("{=typst}", out)

    def test_the_margin_number_precedes_its_own_paragraph(self):
        out = pdfs.preprocess("First. {#para1}\n\nSecond. {#para2}")
        lines = [ln for ln in out.split("\n") if ln.strip()]
        self.assertIn("[1]", lines[0])
        self.assertIn("[2]", lines[1])

    def test_numbers_inside_a_blockquote_are_kept(self):
        """FCJ-047 holds five numbered paragraphs inside one blockquote.

        A block-based version of this took only the last marker in each block
        and lost six of its numbers.
        """
        out = pdfs.preprocess("> Quoted one. {#para42}\n>\n> Quoted two. {#para43}")
        self.assertEqual(out.count("#place(left"), 2)
        for line in out.split("\n"):
            if "#place" in line:
                self.assertTrue(line.lstrip().startswith(">"), line[:60])

    def test_an_empty_numbered_paragraph_gets_no_number(self):
        """The theme numbered some empty paragraphs. Nothing citable there."""
        out = pdfs.preprocess("> {#para65}")
        self.assertNotIn("#place", out)

    def test_embed_becomes_readable_prose(self):
        out = pdfs.preprocess("::: embed\nhttps://player.vimeo.com/video/1\n:::")
        self.assertNotIn(":::", out)
        self.assertIn("not hosted by this archive", out)
        self.assertIn("player.vimeo.com", out)

    def test_preprocessing_loses_no_words(self):
        body = ("## Heading\n\nA paragraph with *italics*. {#para1}\n\n"
                "> A quotation. {#para2}\n\n- A reference entry.\n")
        before = words(markdown.strip_paragraph_numbers(body))
        after = [w for w in words(pdfs.preprocess(body))
                 if w not in {"place", "left", "dx", "dy", "text", "size", "pt",
                              "fill", "luma", "typst", "em", "cm"}]
        for word in before:
            self.assertIn(word, after)


class TestMetadata(unittest.TestCase):
    def test_carries_the_citation_details(self):
        args = pdfs.pandoc_metadata(
            {"title": "A Paper", "authors": ["A Writer"], "fcj_id": "FCJ-001",
             "issue": "1", "published": "2003-11-02", "doi": "10.1/x",
             "abstract": "Claim."}, generated="2026-11-14")
        joined = " ".join(args)
        for expected in ("title=A Paper", "author=A Writer", "fcjid=FCJ-001",
                         "issue=1", "published=2003-11-02", "issn=1449-1443",
                         "generated=2026-11-14"):
            self.assertIn(expected, joined)

    def test_the_licence_defaults_rather_than_being_omitted(self):
        args = " ".join(pdfs.pandoc_metadata({"title": "T"}, generated="x"))
        self.assertIn("licence=Creative Commons BY-NC-ND", args)

    def test_multiple_authors_each_get_their_own_entry(self):
        args = pdfs.pandoc_metadata({"authors": ["One Person", "Two Person"]},
                                    generated="x")
        self.assertEqual(args.count("author=One Person")
                         + args.count("author=Two Person"), 2)

    def test_no_doi_is_minted_for_the_offprint(self):
        """The `doi` passed is the PUBLISHED article's, so a reader can reach
        the version of record. The offprint gets no identifier of its own, or
        the archive has created a second citable object for one paper."""
        args = " ".join(pdfs.pandoc_metadata({"doi": "10.15307/fcj.29.218.2017"},
                                            generated="x"))
        self.assertIn("doi=10.15307/fcj.29.218.2017", args)
        self.assertNotIn("offprint_doi", args)


class TestTemplate(unittest.TestCase):
    def test_the_template_exists_and_states_the_style_it_copies(self):
        with open(pdfs.TEMPLATE, encoding="utf-8") as fh:
            tpl = fh.read()
        self.assertIn("Open Sans", tpl)
        self.assertIn('paper: "a4"', tpl)
        self.assertIn("archival offprint", tpl)

    def test_the_fonts_are_vendored(self):
        """Open Sans is what the journal's later PDFs use, measured with
        pdffonts. Matching it is the single biggest visual factor."""
        self.assertTrue(os.path.isdir(pdfs.FONT_DIR))
        ttfs = [f for f in os.listdir(pdfs.FONT_DIR) if f.lower().endswith(".ttf")]
        self.assertTrue(ttfs, "no TTF in assets/pdf-fonts")

    def test_doi_and_url_are_content_not_typst_strings(self):
        """Pandoc escapes `/` as `\\/` inside a typst string literal, which
        typst rejects — and every DOI and source URL contains slashes."""
        with open(pdfs.TEMPLATE, encoding="utf-8") as fh:
            tpl = fh.read()
        self.assertIn("doi: [$doi$]", tpl)
        self.assertIn("sourceurl: [$sourceurl$]", tpl)


@needs_pandoc
@needs_content
class TestAgainstRealPapers(unittest.TestCase):
    HARD = ["fcj-001", "fcj-047", "fcj-101", "fcj-113"]

    def _typst(self, slug_prefix: str) -> tuple[dict, str, str]:
        name = next(n for n in sorted(os.listdir(os.path.join(CONTENT, "papers")))
                    if n.startswith(slug_prefix))
        with open(os.path.join(CONTENT, "papers", name), encoding="utf-8") as fh:
            meta, body = extract.parse_front_matter(fh.read())
        source = pdfs.preprocess(pdfs.html_tables_to_markdown(body))
        cmd = ["pandoc", "-f", "markdown+raw_html", "-t", "typst",
               "--template", pdfs.TEMPLATE]
        cmd += pdfs.pandoc_metadata(meta, generated="2026-11-14")
        run = subprocess.run(cmd, input=source, capture_output=True, text=True,
                             timeout=600)
        self.assertEqual(run.returncode, 0, run.stderr[:300])
        return meta, body, run.stdout

    def test_no_dialect_syntax_survives_into_the_typst(self):
        for prefix in self.HARD:
            _meta, _body, out = self._typst(prefix)
            self.assertNotIn("{#para", out, prefix)
            self.assertNotIn("::: embed", out, prefix)
            self.assertNotRegex(out, r"(?m)^#{2,6} ", prefix)

    def test_every_citable_paragraph_number_reaches_the_margin(self):
        for prefix in self.HARD:
            _meta, body, out = self._typst(prefix)
            # Markers on paragraphs that actually have text; the theme numbered
            # some empty ones, and FCJ-101 keeps 20 inside a passed-through
            # table where they stay as HTML ids.
            # Anything with content counts, including FCJ-047's `* *` section
            # ornament: the journal numbered it, so it is citable, and dropping
            # its number to tidy the output would renumber nothing but would
            # make the margin disagree with the HTML.
            expected = len([ln for ln in body.split("\n")
                            if re.search(r"\{#para\d+\}", ln)
                            and re.sub(r"[>\s]|\{#para\d+\}", "", ln)])
            self.assertEqual(out.count("#place(left"), expected, prefix)

    def test_apparatus_survives(self):
        _meta, _body, out = self._typst("fcj-120")
        self.assertGreater(out.count("#emph["), 50, "italics")
        self.assertGreater(out.count("#figure("), 5, "figures")
        self.assertGreater(out.count("caption:"), 5, "figure captions")

    def test_the_provenance_colophon_is_in_every_offprint(self):
        for prefix in self.HARD:
            _meta, _body, out = self._typst(prefix)
            self.assertIn("archival offprint", out, prefix)
            self.assertIn("not the publisher", out, prefix)

    def test_an_offprint_carries_no_build_date(self):
        """These 126 PDFs are committed, so they must be byte-identical
        between runs. The code called `date.today()` under a comment claiming
        it was a fixed date, which meant a no-op rebuild rewrote all 126 —
        126 modified binaries for nothing, and a real change invisible in the
        diff. When a file was typeset is the repository's job to record, not
        the file's."""
        args = " ".join(pdfs.pandoc_metadata({"title": "T"}, generated=""))
        self.assertNotIn("generated=", args)
        # The mechanism, not the prose: a grep for "date.today" matched the
        # comment that explains this fix. The module cannot produce a build
        # date if it has no clock.
        self.assertFalse(hasattr(pdfs, "datetime"),
                         "pdfs.py has a clock again; offprints will churn")

    def test_html_tables_keep_their_structure(self):
        """The typst writer emits a raw HTML table's cells as loose text, so
        the table is round-tripped through pandoc's HTML reader first."""
        _meta, body, out = self._typst("fcj-101")
        self.assertIn("<table", body, "fixture assumption: FCJ-101 has a table")
        self.assertIn("#table(", out)


class _TempContent(unittest.TestCase):
    """A content directory whose `offprints/` is disposable.

    `pdfs.build()` writes to `<content_dir>/offprints/` and defaults to the real
    `content/`, so a test that let it render rewrote a COMMITTED offprint. The
    PDFs differed only in typst's document `/ID` — 66 bytes, same length — so
    the archive reported a modified binary for no change in content, on every
    full run of the suite. That is the churn
    `test_an_offprint_carries_no_build_date` exists to prevent: it stops
    `pdfs.py` having a clock, and nothing stopped the tests themselves.

    `build()` reads only `papers/` and resolves figures against `media/`, so
    those are symlinked rather than copied; `offprints/` is the only real
    directory here, and it is thrown away.
    """

    def setUp(self):
        self.content = tempfile.mkdtemp(prefix="fcj-offprints-")
        for name in ("papers", "media"):
            os.symlink(os.path.join(CONTENT, name),
                       os.path.join(self.content, name))
        os.makedirs(os.path.join(self.content, pdfs.OUT_SUBDIR))

    def tearDown(self):
        shutil.rmtree(self.content, ignore_errors=True)


class TestEngineHandling(_TempContent):
    @needs_content
    def test_build_reports_a_missing_engine_rather_than_raising(self):
        report = pdfs.build(content_dir=self.content, engine=None,
                            only=["fcj-001"])
        if ENGINE is None:
            self.assertEqual(report.rendered, [])
            self.assertTrue(report.failed)
            self.assertIn("engine", report.failed[0][1])

    @needs_content
    def test_papers_with_a_publisher_pdf_are_skipped(self):
        report = pdfs.build(content_dir=self.content, only=["fcj-218"])
        self.assertEqual(report.rendered, [])
        self.assertTrue(report.skipped_has_pdf)

    @needs_content
    def test_no_paper_ever_has_both_a_publisher_pdf_and_an_offprint(self):
        """Where the journal published its own PDF, that file is the version of
        record and is kept. Generating a second rendering of the same article
        would put two different-looking documents of one paper into
        circulation, so the split is exact and has no overlap.
        """
        papers = os.path.join(CONTENT, "papers")
        offprints = os.path.join(CONTENT, "offprints")
        both, publisher, generated = [], 0, 0
        for name in sorted(os.listdir(papers)):
            if not name.endswith(".md"):
                continue
            slug = name[:-3]
            with open(os.path.join(papers, name), encoding="utf-8") as fh:
                meta, _ = extract.parse_front_matter(fh.read())
            has_offprint = os.path.isfile(os.path.join(offprints, slug + ".pdf"))
            publisher += bool(meta.get("pdf"))
            generated += has_offprint
            if meta.get("pdf") and has_offprint:
                both.append(slug)
        self.assertEqual(both, [], "a paper has two different PDFs of itself")
        # 237 papers less the two with no recorded author, which get neither.
        self.assertEqual(publisher + generated, 235)

    @needs_content
    def test_papers_with_no_author_are_reported_not_bylined_anonymous(self):
        """FCJ-203 and FCJ-212 carry no citation metadata. A PDF with no byline
        is worse than no PDF for deposit, so they are named, not guessed at."""
        report = pdfs.build(content_dir=self.content,
                            only=["fcj-203", "fcj-212"])
        self.assertTrue(set(report.skipped_no_author) <= {"FCJ-203", "FCJ-212"})


@needs_engine
@needs_content
class TestRendered(_TempContent):
    def test_a_real_pdf_renders_and_retains_its_text(self):
        report = pdfs.build(content_dir=self.content, only=["fcj-001"])
        self.assertEqual(report.failed, [], report.failed)
        self.assertEqual(len(report.rendered), 1)
        pdf = os.path.join(self.content, pdfs.OUT_SUBDIR,
                           report.rendered[0] + ".pdf")
        self.assertTrue(os.path.isfile(pdf))
        if not shutil.which("pdftotext"):
            self.skipTest("pdftotext not available")
        text = subprocess.run(["pdftotext", pdf, "-"], capture_output=True,
                              text=True, timeout=300).stdout
        with open(os.path.join(CONTENT, "papers", "fcj-001.md"), encoding="utf-8") as fh:
            _meta, body = extract.parse_front_matter(fh.read())
        expected = set(words(markdown.strip_paragraph_numbers(body)))
        got = set(words(text))
        missing = expected - got
        self.assertLess(len(missing) / max(len(expected), 1), 0.01,
                        f"{len(missing)} of {len(expected)} words absent")


if __name__ == "__main__":
    unittest.main()
