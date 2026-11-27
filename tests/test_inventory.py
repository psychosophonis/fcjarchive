#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""Tests for build/inventory.py — docs/architecture.md, "API Contracts".

The expensive part is the manifest, and it is the same manifest for every test,
so it is built once per class run rather than per test. These are not unit tests
in the isolated sense: the facts under test are facts about the mirror, and a
fixture would only encode my beliefs about it — which is what went wrong twice
before `resolve.py` existed.
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "build"))

import inventory  # noqa: E402
import resolve  # noqa: E402

HAVE_MIRROR = os.path.isdir(resolve.STATIC_ROOT)
needs_mirror = unittest.skipUnless(HAVE_MIRROR, f"mirror not at {resolve.STATIC_ROOT}")


class TestCitationParsing(unittest.TestCase):
    """No filesystem. Identity comes from the <title>, never the slug."""

    def doc(self, title: str) -> str:
        return f"<html><head><title>{title}</title></head><body></body></html>"

    def test_id_from_title_not_slug(self):
        # issue 16's URLs carry no number at all: /games-of-multitude/ is FCJ-113
        self.assertEqual(
            inventory.fcj_id(self.doc("The Fibreculture Journal: 16 |   FCJ-113 Games of Multitude")),
            "FCJ-113")

    def test_id_is_zero_padded(self):
        # the mirror writes FCJ-002 and fcj002 and FCJ-2; one canonical form
        self.assertEqual(inventory.fcj_id(self.doc("x | FCJ-2 Something")), "FCJ-002")

    def test_mesh_citation(self):
        self.assertEqual(
            inventory.fcj_id(self.doc("The Fibreculture Journal: Mesh | FCJMesh-002 : On Networked Utopias")),
            "FCJMesh-002")

    def test_no_citation_is_none(self):
        self.assertIsNone(inventory.fcj_id(self.doc("The Fibreculture Journal : 01")))

    def test_body_citations_are_ignored(self):
        """A paper's bibliography cites other papers by number.

        Searching the body would hand a paper its bibliography's identity, so
        only the <title> is consulted. This is the test that keeps it that way.
        """
        doc = ('<html><head><title>The Fibreculture Journal: 16 | FCJ-113 Games of Multitude'
               '</title></head><body><p>see FCJ-099 and FCJ-001</p></body></html>')
        self.assertEqual(inventory.fcj_id(doc), "FCJ-113")

    def test_display_title_drops_site_and_citation(self):
        t = inventory.display_title(self.doc(
            "The Fibreculture Journal : 29 |   FCJ-218 Train Ticket Sharing"))
        self.assertEqual(t, "Train Ticket Sharing")


class TestContentExtraction(unittest.TestCase):
    """No filesystem: the balanced-div scan, which a regex cannot do."""

    def test_nested_divs_do_not_truncate(self):
        doc = ('<div id="post_content">a<div class="x">b</div>c</div><div>after</div>')
        self.assertEqual(inventory.extract_region(doc, "post_content"),
                         'a<div class="x">b</div>c')

    def test_missing_container_is_empty(self):
        self.assertEqual(inventory.extract_region("<div id='other'>x</div>", "post_content"), "")

    def test_unclosed_container_keeps_the_rest(self):
        # losing text silently is the failure mode; keeping too much is visible
        self.assertEqual(inventory.extract_region('<div id="post_content">tail', "post_content"),
                         "tail")


class TestDuplicateDetection(unittest.TestCase):
    def test_short_stubs_do_not_collapse(self):
        self.assertFalse(inventory.duplicates("<p>Issue 8</p>", "<p>Issue 9</p>"))

    def test_same_long_text_collapses(self):
        text = "<p>" + ("the editorial of this issue argues that " * 40) + "</p>"
        self.assertTrue(inventory.duplicates(text, text + "<p>plus a paper list</p>"))

    def test_different_long_text_does_not(self):
        a = "<p>" + ("alpha " * 200) + "</p>"
        b = "<p>" + ("beta " * 200) + "</p>"
        self.assertFalse(inventory.duplicates(a, b))


@needs_mirror
class TestManifest(unittest.TestCase):
    man: inventory.Manifest

    @classmethod
    def setUpClass(cls):
        cls.man = inventory.build()

    def test_all_31_issue_hosts_present(self):
        self.assertEqual(len(self.man.issues), 31)
        self.assertIn("mesh", self.man.issues)

    def test_accounting_balances(self):
        """Every page link an issue root carries lands in exactly one bucket.

        This is the test the whole module exists for. Both throwaway inventories
        written before `resolve.py` produced totals that looked complete and
        silently dropped 46 references between them; nothing in their output
        said so. An accounting identity is the cheapest thing that would have.
        """
        self.assertEqual(inventory.check_accounting(self.man), [])

    def test_nothing_is_assigned_a_guessed_identity(self):
        for page in self.man.unclassified:
            self.assertIsNone(inventory.fcj_id(inventory.read(page.source)),
                              f"{page.url} has a citation and should be a paper")

    def test_unresolved_references_are_reported_with_their_source(self):
        """Issue 15's root links seven retired `issue15_<author>.html` pages.

        Verified absent from the entire mirror by `find`, so they are stale
        links to a convention the journal dropped — not missing content: all
        seven of issue 15's papers resolve under their FCJ slugs. The point of
        the test is that they appear in `unresolved` rather than vanishing.
        """
        stale = [u.url for u in self.man.unresolved if u.issue == "15" and u.kind == "page"]
        self.assertEqual(len(stale), 7)
        self.assertTrue(all("issue15_" in u for u in stale))

    def test_issue_16_games_of_multitude_is_a_paper_not_a_duplicate(self):
        """The duplicate-editorial test must not eat a real paper.

        `games-of-multitude` is 15,482 words against issue 16's 6,469-word root
        and was flagged in fcj-problems.md P4 as an unexplained anomaly. It is
        FCJ-113. A duplicate test based on word-count proximity would have
        discarded it.
        """
        self.assertIn("FCJ-113", self.man.papers)
        self.assertEqual(self.man.papers["FCJ-113"].issue, "16")
        self.assertEqual(self.man.papers["FCJ-113"].slug, "games-of-multitude")

    def test_known_duplicate_editorial_collapses(self):
        """Issue 8's standalone editorial does not also appear as a paper."""
        self.assertEqual(self.man.issues["8"].editorial_source, "mirror-standalone")
        slugs = {self.man.papers[i].slug for i in self.man.issues["8"].papers}
        self.assertNotIn("issue-08-editorial", slugs)

    def test_editorial_attribution_ignores_the_slug(self):
        """`nineteen…/issue-1-ubiquity` is issue 19's editorial.

        The slug reads as issue 1. Attribution comes from the host the page was
        found on. This is the same error `proofs/editorial-recovery.py`
        falsified for the dump, in the one place it could still happen.
        """
        self.assertEqual(self.man.issues["19"].editorial_source, "mirror-standalone")
        self.assertIn("issue-1-ubiquity", self.man.issues["19"].editorial_path)
        self.assertNotIn("ubiquity", (self.man.issues["1"].editorial_path or ""))

    def test_fcj_129_is_recovered_from_the_apex_collision_suffix(self):
        """FCJ-129's only copy is `fibreculturejournal.org/fcj-129-…-cultures-3`.

        Issue 19's root links it without the suffix, no rule in
        fcj-redirects.conf mentions it, and no copy exists on `nineteen.`.
        Without the collision-suffix fallback the paper is absent from the
        archive, and nothing in the old audit noticed.
        """
        self.assertIn("FCJ-129", self.man.papers)
        self.assertIn("FCJ-129", self.man.apex_sourced)
        self.assertEqual(self.man.papers["FCJ-129"].issue, "19")

    def test_completeness_227_of_228(self):
        """Invariant 3. FCJ-222 is the only number with no page anywhere."""
        missing = [n for n in range(1, 229) if f"FCJ-{n:03d}" not in self.man.papers]
        self.assertEqual(missing, [222])

    def test_every_absent_number_is_listed_with_a_reason(self):
        """Invariant 3's other half.

        A bare list of gaps reads as an oversight. The reason is what stops the
        next person spending a day rediscovering that FCJ-222 cannot be
        recovered from anything the archive holds.
        """
        listed = inventory.read_known_absent()
        self.assertEqual(sorted(listed), inventory.absent_numbers(self.man))
        for ident, reason in listed.items():
            self.assertGreater(len(reason), 60, ident)
            self.assertNotIn("INVESTIGATE", reason, ident)

    def test_the_absent_list_is_generated_not_hand_written(self):
        with open(inventory.KNOWN_ABSENT, encoding="utf-8") as fh:
            head = fh.read(400)
        self.assertIn("GENERATED", head)
        self.assertIn("inventory.py", head)

    def test_writing_the_absent_list_is_deterministic(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            first = os.path.join(tmp, "a.txt")
            second = os.path.join(tmp, "b.txt")
            inventory.write_known_absent(self.man, first)
            inventory.write_known_absent(self.man, second)
            self.assertEqual(inventory.read(first), inventory.read(second))

    def test_every_issue_has_editorial_text_from_the_mirror(self):
        """Invariant 4, satisfied by the mirror alone — no dump needed.

        This corrects fcj-problems.md P5, which claimed issues 1, 2, 5 and 23
        had no editorial anywhere in `fcj-static/` and could only be recovered
        from the WordPress dump. That audit walked the four ISSUE SUBDOMAINS.
        The editorials are on the APEX host at `/issue-NN-editorial/`, where 14
        of them sit (issues 1-14), and issue 23's is on its own host under a
        themed slug. All three apex copies were checked for the known injection
        and are clean.
        """
        for number, iss in self.man.issues.items():
            self.assertNotEqual(iss.editorial_source, "absent", f"issue {number}")
            self.assertGreater(inventory.words(iss.editorial_html), 0, f"issue {number}")

    def test_the_four_formerly_lost_editorials_are_in_the_mirror(self):
        for number in ("1", "2", "5", "23"):
            iss = self.man.issues[number]
            self.assertEqual(iss.editorial_source, "mirror-standalone", f"issue {number}")
            self.assertGreater(inventory.words(iss.editorial_html), 300, f"issue {number}")

    def test_thin_editorials_are_a_known_set(self):
        """The short ones, so a regression in extraction is visible.

        Under 1,000 words of editorial prose. Not a defect in itself — issue 2's
        editorial really is 432 words — but if this set grows, the content
        extraction has broken somewhere and the generator would publish stubs.
        """
        thin = sorted(n for n, iss in self.man.issues.items()
                      if inventory.words(iss.editorial_html) < 1000)
        self.assertEqual(thin, ["1", "2", "23", "5", "mesh"])

    def test_a_code_theme_is_distinguished_from_the_shared_asset_bucket(self):
        """`wp-content/themes` holds two unlike things, and conflating them is
        destructive in one direction: `themes/fcsharedimg/banners<N>/` is where
        every issue banner lives, so excluding the whole directory would delete
        all 13 of them.

        The test is structural, not a list of names — WordPress requires a
        theme to declare itself in `style.css`.
        """
        root = resolve.STATIC_ROOT
        code = os.path.join(root, "nineteen.fibreculturejournal.org",
                            "wp-content", "themes", "fcjissue19", "PDFicon.gif")
        bucket = os.path.join(root, "nineteen.fibreculturejournal.org",
                              "wp-content", "themes", "fcsharedimg",
                              "thumbs", "istwo.jpg")
        upload = os.path.join(root, "fibreculturejournal.org", "wp-content",
                              "uploads", "2015", "01", "x.jpg")
        self.assertTrue(inventory.in_code_theme(code))
        self.assertFalse(inventory.in_code_theme(bucket),
                         "fcsharedimg holds the banners; it is not a code theme")
        self.assertFalse(inventory.in_code_theme(upload))

    def test_no_theme_chrome_is_collected_as_an_asset(self):
        """The old theme's `PDFicon.gif`, `epub.gif` and `favicon2.ico` are
        interface from a design that is gone. The archive prints those links
        as text."""
        chrome = [rel for rel in self.man.assets
                  if inventory.in_code_theme(os.path.join(resolve.STATIC_ROOT, rel))]
        self.assertEqual(chrome, [])

    def test_shared_issue_artwork_is_still_collected(self):
        """The other direction. Excluding too much here is how the banners
        would disappear, so assert the bucket is reachable at all."""
        self.assertTrue(
            os.path.isdir(os.path.join(resolve.STATIC_ROOT,
                                       "nineteen.fibreculturejournal.org",
                                       "wp-content", "themes", "fcsharedimg")))
        self.assertFalse(os.path.isfile(os.path.join(
            resolve.STATIC_ROOT, "nineteen.fibreculturejournal.org",
            "wp-content", "themes", "fcsharedimg", "style.css")),
            "if fcsharedimg ever gains a style.css the banners drop out")

    def test_inputs_were_not_modified(self):
        """Invariant 6. The build is read-only over the mirror."""
        before = os.stat(resolve.STATIC_ROOT).st_mtime
        inventory.build()
        self.assertEqual(os.stat(resolve.STATIC_ROOT).st_mtime, before)


class TestNoEditorialIsABlogIndex(unittest.TestCase):
    """An issue root can be a list of truncated post excerpts.

    `inventory` prefers a standalone editorial over the issue root because the
    root repeats the paper list that the generator writes from the manifest.
    Mesh never got that benefit: `EDITORIAL_SLUG` is `^issue-\\d{1,2}` and mesh
    is the only issue that is not numbered, so nothing could match. It kept the
    WordPress front page — nine post excerpts, each ending in a "read more"
    ellipsis pointing nowhere, three of them duplicating the table of contents
    rendered directly below them.
    """

    CONTENT = os.path.join(ROOT, "content")
    ELLIPSIS = "…]"

    @unittest.skipUnless(os.path.isdir(os.path.join(ROOT, "content", "issues")),
                         "content/ not built")
    def test_no_issue_editorial_ends_a_paragraph_in_a_read_more_ellipsis(self):
        issues = os.path.join(self.CONTENT, "issues")
        offenders = []
        for name in sorted(os.listdir(issues)):
            if not name.endswith(".md"):
                continue
            with open(os.path.join(issues, name), encoding="utf-8") as fh:
                if self.ELLIPSIS in fh.read():
                    offenders.append(name)
        self.assertEqual(offenders, [],
                         "an editorial is a blog index of truncated excerpts, "
                         "not an editorial")

    @needs_mirror
    def test_mesh_resolves_to_its_about_page_not_its_root(self):
        self.assertEqual(inventory.EDITORIAL_BY_SLUG.get("mesh"), "about-mesh")
        man = inventory.build()
        mesh = man.issues.get("mesh")
        self.assertIsNotNone(mesh, "mesh is missing from the manifest")
        self.assertEqual(mesh.editorial_source, "mirror-standalone")
        self.assertNotIn(self.ELLIPSIS, mesh.editorial_html)


if __name__ == "__main__":
    unittest.main()
