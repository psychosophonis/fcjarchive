#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""Tests for build/markdown.py — docs/architecture.md, "Content format".

The dialect is closed: this project writes the Markdown and this project reads
it. These tests exist to keep the two halves honest about each other, because
nothing else would notice if the writer started emitting something the reader
silently drops.

The round-trip tests run against real papers. The conversion's job is to
survive the mirror's actual markup, and a fixture would only encode what I
believe that markup is.
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "build"))

import inventory  # noqa: E402
import markdown  # noqa: E402
import resolve  # noqa: E402

HAVE_MIRROR = os.path.isdir(resolve.STATIC_ROOT)
needs_mirror = unittest.skipUnless(HAVE_MIRROR, f"mirror not at {resolve.STATIC_ROOT}")

# One paper per awkward feature, chosen by measuring the whole mirror.
HARD = ["FCJ-001", "FCJ-218", "FCJ-120", "FCJ-019", "FCJ-101", "FCJ-047", "FCJ-113"]


def words(text: str) -> list[str]:
    return [w for w in re.findall(r"[\w’'-]+", text.lower()) if w.strip("-'’")]


def visible_text(html: str) -> str:
    h = re.sub(r"(?s)<[^>]+>", " ", html)
    import html as htmllib
    return htmllib.unescape(h)


class TestDialectRoundTrip(unittest.TestCase):
    """Pure: every construct the writer emits, read back by the renderer."""

    def test_paragraph_number_becomes_id_and_rail(self):
        html = markdown.render("Some text here. {#para76}")
        self.assertIn('id="para76"', html)
        self.assertIn('class="rail"', html)
        self.assertIn(">76</a>", html)
        self.assertNotIn("{#para76}", html)

    def test_paragraph_without_a_number_is_still_a_paragraph(self):
        html = markdown.render("A caption or an unnumbered block.")
        self.assertIn("<p>", html)
        self.assertNotIn("rail", html)

    def test_numbered_paragraph_inside_a_blockquote(self):
        """1,514 numbered paragraphs are inside quotations.

        Handling the suffix only in the plain-paragraph branch printed the raw
        `{#para15}` marker to the reader in every one of them.
        """
        html = markdown.render("> Quoted fieldnote. {#para15}")
        self.assertIn("<blockquote>", html)
        self.assertIn('id="para15"', html)
        self.assertNotIn("{#para15}", html)

    def test_emphasis_and_strong(self):
        html = markdown.render("The *Journal of Nothing* and **bold** text.")
        self.assertIn("<em>Journal of Nothing</em>", html)
        self.assertIn("<strong>bold</strong>", html)

    def test_figure_gets_a_numbered_caption(self):
        html = markdown.render("![A view of the thing](/media/x.jpg)")
        self.assertIn("<figure>", html)
        self.assertIn("<figcaption>Figure 1. A view of the thing</figcaption>", html)
        self.assertIn('alt="A view of the thing"', html)

    def test_caption_that_numbers_itself_is_not_renumbered(self):
        html = markdown.render("![Figure 3. Something](/media/x.jpg)")
        self.assertIn("<figcaption>Figure 3. Something</figcaption>", html)
        self.assertNotIn("Figure 1. Figure 3", html)

    def test_figures_number_in_document_order(self):
        html = markdown.render("![One](/a.jpg)\n\n![Two](/b.jpg)")
        self.assertIn("Figure 1. One", html)
        self.assertIn("Figure 2. Two", html)

    def test_note_references_are_linked_to_their_notes(self):
        """Rebuilt from structure, which is why losing 1,905 `<a name>` anchors
        in the mirror costs nothing."""
        html = markdown.render("Claim in the text. [1] {#para2}\n\n"
                               "## Notes\n\n[1] The note itself.")
        self.assertIn('id="noteref-1"', html)
        self.assertIn('href="#note-1"', html)
        self.assertIn('id="note-1"', html)
        self.assertIn('href="#noteref-1"', html)   # the back-link

    def test_bracket_numbers_are_left_alone_when_there_are_no_notes(self):
        html = markdown.render("A range of [1] to [5] in a table caption.")
        self.assertNotIn("noteref", html)

    def test_reference_list_is_marked_for_hanging_indent(self):
        html = markdown.render("## References\n\n- Bauman, Zygmunt. *The Individualized Society*.")
        self.assertIn('class="reflist"', html)

    def test_headings_keep_their_level_and_get_an_anchor(self):
        html = markdown.render("### Introduction")
        self.assertIn('<h3 id="introduction">Introduction</h3>', html)

    def test_table_passes_through_as_html(self):
        html = markdown.render("<table><tr><td>a</td></tr></table>")
        self.assertIn("<table>", html)
        self.assertIn("<td>a</td>", html)

    def test_embed_becomes_a_visible_statement_of_what_is_missing(self):
        html = markdown.render("::: embed\nhttps://player.vimeo.com/video/1\n:::")
        self.assertIn('class="embed"', html)
        self.assertIn("player.vimeo.com", html)

    def test_html_in_the_text_is_escaped(self):
        html = markdown.render("A claim about <script>alert(1)</script> injection.")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_strip_paragraph_numbers_is_the_documented_regex(self):
        md = "First. {#para1}\n\nSecond. {#para2}\n"
        self.assertEqual(markdown.strip_paragraph_numbers(md),
                         "First.\n\nSecond.\n")


class TestEmphasisSpacing(unittest.TestCase):
    def test_space_inside_the_tag_moves_outside_the_markers(self):
        """`<em>Uzume </em>(2002)` must not become `*Uzume*(2002)`.

        Squeezing the inner text without replacing the space ran words together
        in 1,153 places across the corpus — "Uzume(2002)".
        """
        md = markdown.to_markdown("<p><em>Uzume </em>(2002) is a work.</p>")
        self.assertIn("*Uzume* (2002)", md)

    def test_leading_space_too(self):
        md = markdown.to_markdown("<p>the<em> Journal</em> of</p>")
        self.assertIn("the *Journal* of", md)


class TestCitationMetadata(unittest.TestCase):
    def test_authors_from_citation_tags(self):
        doc = ('<meta name="citation_author" content="Ned Rossiter">'
               '<meta name="citation_author" content="Soenke Zehle">')
        self.assertEqual(markdown.authors(doc), ["Ned Rossiter", "Soenke Zehle"])

    def test_attribute_order_does_not_matter(self):
        doc = '<meta content="Ned Rossiter" name="citation_author">'
        self.assertEqual(markdown.authors(doc), ["Ned Rossiter"])

    def test_doi_from_the_body_when_not_in_a_meta_tag(self):
        self.assertEqual(markdown.doi("", "**doi:**10.15307/fcj.29.218.2017 and more"),
                         "10.15307/fcj.29.218.2017")

    def test_published_date_is_normalised(self):
        doc = '<meta name="citation_publication_date" content="2017/06/29">'
        self.assertEqual(markdown.published(doc), "2017-06-29")


@needs_mirror
class TestAgainstRealPapers(unittest.TestCase):
    man: inventory.Manifest

    @classmethod
    def setUpClass(cls):
        cls.man = inventory.build()

    def test_no_word_is_lost_converting_real_papers(self):
        """The finding `proofs/markdown-fidelity.py` rests on, as a test.

        Compared as a multiset of words, ignoring punctuation, because that is
        what "the text is preserved" means. The paragraph-number rail that the
        theme printed as " - 76 - " is removed from the source side first: it is
        apparatus the archive carries as `{#para76}` instead, not prose.
        """
        for ident in HARD:
            paper = self.man.papers.get(ident)
            if paper is None:
                continue
            content = inventory.content_of(inventory.read(paper.source))
            for pattern in markdown.BOILERPLATE:
                content = pattern.sub("", content)
            source = markdown.LINENO_SPAN.sub("", content)
            md = markdown.to_markdown(content)
            # Both sides go through `visible_text`: a parked table keeps its
            # HTML entities, so comparing an unescaped source against a raw
            # Markdown string reported `don&#8217;t` as a lost "don’t".
            lost = Counter(words(visible_text(source))) - Counter(
                words(visible_text(markdown.strip_paragraph_numbers(md))))
            # `19<sup>th</sup>` legitimately joins into one token, so a handful
            # of single-token joins are expected; wholesale loss is not.
            self.assertLess(sum(lost.values()), 10,
                            f"{ident} lost {sum(lost.values())} words: "
                            f"{list(lost.elements())[:8]}")

    def test_rendering_real_papers_leaks_no_dialect_syntax(self):
        for ident in HARD:
            paper = self.man.papers.get(ident)
            if paper is None:
                continue
            md = markdown.to_markdown(inventory.content_of(inventory.read(paper.source)))
            html = markdown.render(md)
            self.assertNotIn("{#para", html, f"{ident} leaked a paragraph marker")
            self.assertNotIn("::: embed", html, f"{ident} leaked an embed fence")
            self.assertNotRegex(html, r"(?m)^#{2,6} ", f"{ident} leaked a heading marker")

    def test_paragraph_numbers_survive_conversion(self):
        """Both markup variants, measured per paper rather than assumed."""
        for ident in HARD:
            paper = self.man.papers.get(ident)
            if paper is None:
                continue
            content = inventory.content_of(inventory.read(paper.source))
            # Paragraphs inside a table are excluded: the table is passed
            # through as HTML, so those paragraphs keep their native
            # `id="paraN"` and their citation numbers survive in the output
            # without ever becoming `{#paraN}`. FCJ-101 lays out 20 numbered
            # paragraphs in a two-column table that way.
            content = re.sub(r"(?is)<table\b.*?</table>", " ", content)
            # Numbered paragraphs that hold no text are excluded. FCJ-101 has
            # `<p id='para97'><em> </em></p>` — the theme numbered an empty
            # paragraph. Carrying the number would put an empty paragraph in
            # the archive; dropping it loses nothing citable.
            expected = {n for n, body in re.findall(
                r"""(?is)<p[^>]*\bid=['"]para(\d+)['"][^>]*>(.*?)</p>""", content)
                if re.sub(r"(?s)<[^>]+>|\s|&nbsp;", "", body)}
            md = markdown.to_markdown(content)
            got = set(re.findall(r"\{#para(\d+)\}", md))
            missing = expected - got
            self.assertEqual(missing, set(), f"{ident} dropped paragraph ids {sorted(missing)[:8]}")

    def test_quoted_markup_becomes_a_code_span(self):
        """FCJ-127 prints XML in its argument, escaped in the source."""
        md = markdown.to_markdown("<p>the &lt;annotation&gt; element</p>")
        self.assertIn("`<annotation>`", md)
        html = markdown.render(md)
        self.assertIn("<code>&lt;annotation&gt;</code>", html)
        self.assertNotIn("<annotation>", html)

    def test_a_less_than_sign_in_prose_is_not_treated_as_markup(self):
        md = markdown.to_markdown("<p>where x &lt; y holds</p>")
        self.assertNotIn("`", md)
        self.assertIn("x < y", md)

    def test_fcj_047_recovers_its_inline_numbered_paragraphs(self):
        """FCJ-047 prints 39 of its numbers in the paragraph text, not in an id.

        A rule that read only ids would declare those paragraphs unnumbered and
        the archive would renumber them, breaking citations to them.
        """
        paper = self.man.papers["FCJ-047"]
        md = markdown.to_markdown(inventory.content_of(inventory.read(paper.source)))
        numbers = [int(n) for n in re.findall(r"\{#para(\d+)\}", md)]
        self.assertGreater(len(numbers), 85)
        self.assertEqual(numbers, sorted(numbers), "numbers must stay in document order")


if __name__ == "__main__":
    unittest.main()
