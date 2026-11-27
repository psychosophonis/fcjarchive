# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""The audit is the thing that replaces whack-a-mole, so it is itself tested.

Five defects in one session were found by a person reading pages. Each was
fixed with a one-off rule, which scales with how many of 275 pages someone
reads. These tests assert two different things:

  1. the audit's enforced categories are CLEAN — the class cannot come back
  2. the audit's checks are CORRECT — each fires on the real residue and not
     on the authored text it sits next to

The second matters as much as the first. Two of these checks were wrong when
first written: `deep-heading` flagged five authored subsections in a paper on
falling robots, and `empty-link` flagged uncaptioned figures as broken links.
Acting on either would have damaged content to satisfy a tool.
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content")
sys.path.insert(0, os.path.join(ROOT, "build"))

import audit_content  # noqa: E402

HAVE_CONTENT = os.path.isdir(os.path.join(CONTENT, "papers"))
needs_content = unittest.skipUnless(HAVE_CONTENT, "content/ not built")


class TestTheChecks(unittest.TestCase):
    """Each check, against the residue it is for and the prose it must spare."""

    def test_download_labels_including_runs(self):
        fires = audit_content.DOWNLOAD_LABEL.search
        self.assertTrue(fires("Issue: pdf"))
        self.assertTrue(fires("Editorial:pdf"))
        # The run, with no separator and a four-space indent — issue 20's,
        # which the earlier one-pair-per-line rule missed entirely.
        self.assertTrue(fires("    Issue:ePubIssue:pdf   Editorial:pdf"))
        # Prose that merely mentions them.
        self.assertFalse(fires("The editorial is available as a PDF below."))
        self.assertFalse(fires("Issue: a question of method"))

    def test_nav_menu_spares_the_authored_separator(self):
        fires = audit_content.NAV_MENU.search
        self.assertTrue(fires(":: editorial policy"))
        self.assertTrue(fires("  :: guidelines for submission"))
        # The About page uses `::` mid-line as an authored separator, and
        # `::: embed` is a fence in this archive's dialect. A rule that simply
        # deleted `::` would destroy both.
        self.assertFalse(fires("media innovation, and their critique :: "
                               "national strategies for innovation"))
        self.assertFalse(fires("::: embed"))

    def test_deep_headings_are_only_furniture_outside_papers(self):
        """The check that was wrong. In an issue page `#####` is the old theme
        using heading level as a font size. In a paper it is an author's
        structure: FCJ-210 nests five levels for the phases of a fall."""
        self.assertEqual(audit_content.SCOPED["deep-heading"],
                         ("issues/", "pages/"))
        self.assertTrue(audit_content.DEEP_HEADING.search("##### Comparisons"))
        self.assertFalse(audit_content.DEEP_HEADING.search("### Comparisons"))

    def test_empty_link_is_not_an_uncaptioned_figure(self):
        """The other check that was wrong. `![](src)` is a figure whose caption
        was not found — a real concern, since 69 captions were once lost to
        `alt` attributes — but it is not a broken link, and deleting it would
        delete the figure."""
        self.assertTrue(audit_content.EMPTY_LINK.search("[FCJ Guidelines]()"))
        self.assertFalse(audit_content.EMPTY_LINK.search("![](../media/x.jpg)"))
        self.assertTrue(audit_content.UNCAPTIONED_FIGURE.search("![](../media/x.jpg)"))
        self.assertFalse(audit_content.UNCAPTIONED_FIGURE.search(
            "![Figure 1. A diagram.](../media/x.jpg)"))

    def test_remote_images_are_detected_by_host(self):
        """`journal.fibreculture.org` is a different domain from
        `fibreculturejournal.org` and is not in the mirror, so these resolve
        nowhere."""
        self.assertTrue(audit_content.REMOTE_IMAGE.search(
            "![A work](https://journal.fibreculture.org/images/godot.jpg)"))
        self.assertFalse(audit_content.REMOTE_IMAGE.search(
            "![A work](../media/six.fibreculturejournal.org/files/x.jpeg)"))

    def test_generic_theme(self):
        fires = audit_content.GENERIC_THEME.match
        self.assertTrue(fires('"Fibreculture Journal: 20"'))
        self.assertTrue(fires('"The Fibreculture Journal : 29"'))
        self.assertFalse(fires('Issue 20 – Networked Utopias and Speculative Futures'))
        self.assertFalse(fires('"Issue 23: General Issue"'))

    def test_numbered_apparatus_uses_the_trailing_run(self):
        """A second, independent implementation of the rule in `extract`. If
        one drifts the other notices, which a shared helper could not do."""
        body = ["## Note", "", "an aside {#para2}", "",
                "## Discussion", "", "argument {#para3}", "",
                "## References", "", "Somebody (2001) {#para4}"]
        self.assertEqual(audit_content.numbered_apparatus(body, set()), 8)
        clean = body[:-1] + ["Somebody (2001)"]
        self.assertIsNone(audit_content.numbered_apparatus(clean, set()))
        # A mid-text Note followed by a real section must not be the cut.
        midtext = ["## Note", "", "an aside {#para2}", "",
                   "## Discussion", "", "argument {#para3}"]
        self.assertIsNone(audit_content.numbered_apparatus(midtext, set()))

    def test_fences_are_skipped(self):
        """This archive parks raw HTML tables inside backticks, so a check that
        read inside fences would flag every table in the archive."""
        body = ["before", "```", "##### not a heading", "```", "after"]
        self.assertEqual(audit_content.fenced(body), {1, 2, 3})

    def test_front_matter_is_parsed_without_the_extractor(self):
        """Deliberately not shared with `extract`: an audit that uses the same
        parser as the thing it audits cannot see a defect in that parser."""
        front, body = audit_content.split_front_matter(
            "---\ntitle: x\n---\n\nbody\n")
        self.assertEqual(front, ["title: x"])
        self.assertEqual(body, ["", "body"])


@needs_content
class TestTheArchiveIsClean(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.report = audit_content.audit(CONTENT)

    def test_no_enforced_category_has_a_hit(self):
        """The one that replaces being told. Every category here had hits that
        were read and confirmed to be platform furniture, not authored text."""
        hits = self.report.enforced()
        self.assertEqual(
            [f"{h.category} {h.path}:{h.line} {h.text}" for h in hits], [])

    def test_only_the_unrecoverable_figures_are_still_remote(self):
        """Was 68 figures in 9 early papers, all pointing at
        `journal.fibreculture.org` — a domain outside the crawl with no copy
        in the mirror. 83 of the 85 referenced files are now recovered from
        the Wayback Machine, and no figure is still remote. What is left out
        is what the Internet Archive itself does not hold, and neither is an
        image:

          - `issue10/roundtable/roundtable.mov` — no snapshot
          - `issue7_BtMW_FC_visualization.pdf` — snapshot TRUNCATED at source,
            130,710 of 2,280,778 bytes; 6% of a PDF is not the PDF, so it is
            refused rather than written out as though it opened

        Pinned at 3 rather than at the current 0, deliberately: a pin set to
        the exact count turns any later recovery into a test failure, which
        teaches the next person to loosen the pin instead of reading it. A
        regression in the rewriting still shows up, because it would put back
        tens of figures, not one.
        """
        remote = [h for h in self.report.hits if h.category == "remote-image"]
        self.assertLessEqual(
            len(remote), 3,
            [f"{h.path}:{h.line} {h.text}" for h in remote])

    def test_the_audit_is_runnable_as_a_command(self):
        """It has to be usable on its own, not only through the test suite —
        each capability here is a separate executable over files."""
        self.assertTrue(os.access(
            os.path.join(ROOT, "build", "audit_content.py"), os.R_OK))
        self.assertTrue(audit_content.ENFORCED)


if __name__ == "__main__":
    unittest.main()
