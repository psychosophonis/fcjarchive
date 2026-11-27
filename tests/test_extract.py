#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""Tests for build/extract.py — docs/architecture.md, "Content format".

`content/` is the archive. If something is wrong in here, it is wrong in the
thing people download and cite, and re-extracting invalidates everything
downstream — so these tests check the committed files rather than only the
functions that write them.
"""
from __future__ import annotations

import glob
import os
import re
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content")
sys.path.insert(0, os.path.join(ROOT, "build"))

import extract  # noqa: E402
import inventory  # noqa: E402
import markdown  # noqa: E402
import resolve  # noqa: E402

HAVE_CONTENT = os.path.isdir(os.path.join(CONTENT, "papers"))
needs_content = unittest.skipUnless(HAVE_CONTENT, "content/ not built; run build/extract.py")


class TestFrontMatter(unittest.TestCase):
    """Pure: the small YAML subset must survive a round trip."""

    def test_round_trip_scalars_and_lists(self):
        fields = {"fcj_id": "FCJ-218", "authors": ["Paula Bialski", "A N Other"],
                  "issue": "29"}
        text = extract.dump_front_matter(fields) + "Body text.\n"
        back, body = extract.parse_front_matter(text)
        self.assertEqual(back["fcj_id"], "FCJ-218")
        self.assertEqual(back["authors"], ["Paula Bialski", "A N Other"])
        self.assertEqual(body, "Body text.\n")

    def test_titles_with_colons_are_quoted_and_survive(self):
        """FCJ titles are full of colons — "Babylonian Dreams: From Info-Cities
        to Smart Cities" — and an unquoted colon would make the parser read the
        title as a nested key."""
        title = "Babylonian Dreams: From Info-Cities to Smart Cities"
        text = extract.dump_front_matter({"title": title}) + "x\n"
        back, _ = extract.parse_front_matter(text)
        self.assertEqual(back["title"], title)

    def test_quotes_inside_values_survive(self):
        value = 'A paper about "smartness" and other things'
        back, _ = extract.parse_front_matter(
            extract.dump_front_matter({"title": value}) + "x\n")
        self.assertEqual(back["title"], value)

    def test_empty_fields_are_omitted_rather_than_written_blank(self):
        text = extract.dump_front_matter({"doi": "", "pdf": None, "title": "T"})
        self.assertNotIn("doi:", text)
        self.assertNotIn("pdf:", text)
        self.assertIn("title: T", text)

    def test_a_file_without_front_matter_is_all_body(self):
        fields, body = extract.parse_front_matter("Just text.\n")
        self.assertEqual(fields, {})
        self.assertEqual(body, "Just text.\n")


class TestSplittingOutMetadata(unittest.TestCase):
    def test_abstract_is_lifted_out_of_the_body(self):
        abstract, body = extract.take_abstract(
            "**Abstract:** The claim of the paper.\n\n## Introduction\n\nText.")
        self.assertEqual(abstract, "The claim of the paper.")
        self.assertNotIn("Abstract", body)

    def test_abstract_on_its_own_line_takes_the_following_block(self):
        abstract, _ = extract.take_abstract("**Abstract**\n\nThe claim.\n\nMore.")
        self.assertEqual(abstract, "The claim.")

    def test_a_paper_discussing_abstraction_is_not_mistaken_for_an_abstract(self):
        abstract, body = extract.take_abstract("Abstraction is the subject here.")
        self.assertEqual(abstract, "")
        self.assertIn("Abstraction", body)

    def test_byline_is_removed_only_when_it_matches_the_citation_metadata(self):
        body = "#### **Paula Bialski**\n\nLeuphana University\n\n## Introduction\n\nText."
        affiliation, rest = extract.take_byline(body, ["Paula Bialski"])
        self.assertEqual(affiliation, "Leuphana University")
        self.assertTrue(rest.startswith("## Introduction"))

    def test_prose_that_names_the_author_is_left_alone(self):
        """The author's name in the first sentence of the argument is text, not
        a byline. Only short leading blocks are candidates."""
        body = ("As Paula Bialski argues at length in her earlier work on this "
                "question, the smart city is not only digital, and this paper "
                "takes that argument somewhere else entirely.")
        affiliation, rest = extract.take_byline(body, ["Paula Bialski"])
        self.assertEqual(affiliation, "")
        self.assertEqual(rest, body)

    def test_editors_from_the_heading_credit(self):
        editors, body = extract.take_editors(
            "###### Issue Edited by Su Ballard, Zita Joyce and Lizzie Muller\n\nText.")
        self.assertEqual(editors, ["Su Ballard", "Zita Joyce", "Lizzie Muller"])
        self.assertNotIn("Edited by", body)

    def test_editors_with_their_institutions(self):
        editors, _ = extract.take_editors(
            "Introduction by **Armin Beverungen** of Leuphana University Lüneburg "
            "and **Florian Sprenger** of Goethe University Frankfurt.")
        self.assertEqual(editors, ["Armin Beverungen, Leuphana University Lüneburg",
                                   "Florian Sprenger, Goethe University Frankfurt"])

    def test_the_conjunction_is_not_part_of_the_institution(self):
        """`[^,.]` ran straight through "and **Florian Sprenger** of …" and gave
        the first editor an institution containing the second editor's name."""
        editors, _ = extract.take_editors(
            "Introduction by **A Person** of Some University and "
            "**B Person** of Other University.")
        self.assertEqual(editors[0], "A Person, Some University")

    def test_a_role_written_into_the_name_is_removed(self):
        """Issue 30 prints `**Lone Bertelsen***, Issue Editor*`, so the role
        ends up inside the name."""
        self.assertEqual(extract.clean_editor_name("**Lone Bertelsen***, Issue Editor*"),
                         "Lone Bertelsen")
        self.assertEqual(extract.clean_editor_name("Andrew Murphie Editor"),
                         "Andrew Murphie")

    def test_edited_by_inside_prose_is_not_a_credit(self):
        """Issues 19 and 25 cite other people's edited books in the editorial —
        "an anthology edited by Ulrik Ekman presents…". Only a heading counts.
        """
        editors, body = extract.take_editors(
            "The anthology edited by Ulrik Ekman presents the first relatively "
            "comprehensive engagement with the field, and is worth reading.")
        self.assertEqual(editors, [])
        self.assertIn("Ulrik Ekman", body)

    def test_editors_from_bios_when_there_is_no_credit_line(self):
        editors, _ = extract.take_editors(
            "[Tanya Notley](https://x/) is a Lecturer in Internet Studies at "
            "Western Sydney University.\n\n"
            "[Jean Burgess](https://y/) is Director of the Digital Media "
            "Research Centre at QUT.")
        self.assertEqual(editors, ["Tanya Notley", "Jean Burgess"])

    def test_issue_furniture_is_stripped(self):
        body = extract.strip_issue_furniture(
            "#### Editorial\n\n####\n\n"
            "![](/media/x.org/wp-content/themes/fcjissue19/PDFicon.gif)\n\n"
            "Issue:pdf\n\nReal editorial text.")
        self.assertNotIn("PDFicon", body)
        self.assertNotIn("Issue:pdf", body)
        self.assertIn("Real editorial text.", body)

    def test_the_hand_written_contents_list_is_removed(self):
        """Four issues take their editorial from the issue ROOT, which ends
        with the issue's own table of contents. The archive generates that list
        and puts it above the editorial, so leaving the original in prints the
        whole issue twice."""
        body = extract.strip_issue_furniture(
            "Editorial prose mentioning [FCJ-218 a paper](/papers/fcj-218-x/) "
            "inside a sentence.\n\n"
            "[FCJ-219 The Sensed Smog](/papers/fcj-219-x/)\n\nJussi Parikka\n\n"
            "[FCJ-220 Imperial Infrastructures](/papers/fcj-220-x/)\n\nNed Rossiter")
        self.assertIn("inside a sentence", body)
        self.assertNotIn("/papers/fcj-219-x/", body)
        self.assertNotIn("Jussi Parikka", body)

    def test_the_issue_doi_moves_to_front_matter(self):
        doi, body = extract.take_issue_doi(
            "**issue doi:**10.15307/fcj.29\n\nEditorial text.")
        self.assertEqual(doi, "10.15307/fcj.29")
        self.assertNotIn("10.15307", body)

    def test_doi_line_is_removed_from_the_body(self):
        body = extract.take_doi_line(
            "**doi:**[10.15307/fcj.29.218.2017](https://dx.doi.org/10.15307/fcj.29.218.2017)"
            "\n\n## Introduction\n\nText.")
        self.assertNotIn("10.15307", body)
        self.assertIn("## Introduction", body)


@needs_content
class TestTheArchiveOnDisk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.papers = {}
        for path in sorted(glob.glob(os.path.join(CONTENT, "papers", "*.md"))):
            with open(path, encoding="utf-8") as fh:
                meta, body = extract.parse_front_matter(fh.read())
            cls.papers[os.path.basename(path)[:-3]] = (meta, body, path)
        cls.issues = {}
        for path in sorted(glob.glob(os.path.join(CONTENT, "issues", "*.md"))):
            with open(path, encoding="utf-8") as fh:
                meta, body = extract.parse_front_matter(fh.read())
            cls.issues[os.path.basename(path)[:-3]] = (meta, body, path)

    def test_every_paper_and_issue_is_present(self):
        self.assertEqual(len(self.papers), 237)
        self.assertEqual(len(self.issues), 31)

    def test_every_paper_has_an_id_a_title_and_an_issue(self):
        for slug, (meta, _body, _p) in self.papers.items():
            self.assertTrue(meta.get("fcj_id"), slug)
            self.assertTrue(meta.get("title"), slug)
            self.assertTrue(meta.get("issue"), slug)

    def test_authorship_is_recorded_for_every_paper(self):
        """Academic presentation needs authors, so an unattributed article is a
        defect, not a detail. Until 2026-11-27 FCJ-203 and FCJ-212 had none:
        they are peer-reviewed issue editorials whose posts carry `issueeditor`
        rather than the `dccreator` the theme turns into `citation_author`.
        They are now declared in `extract.EDITORIAL_AUTHORS`.
        """
        missing = sorted(meta["fcj_id"] for meta, _b, _p in self.papers.values()
                         if not meta.get("authors"))
        self.assertEqual(missing, [])

    def test_editorial_authors_are_the_issue_editors_not_the_managing_editors(self):
        """`issueeditor` lists the journal's managing editors beside the issue's
        own editors, and they did not write the editorial. The two declared
        editorials must credit exactly their issue editors."""
        expected = {
            "FCJ-203": ["Petra Gemeinboeck", "Elena Knox", "Jill Bennett"],
            "FCJ-212": ["Armin Beverungen", "Florian Sprenger"],
        }
        by_id = {meta["fcj_id"]: meta for meta, _b, _p in self.papers.values()}
        for ident, authors in expected.items():
            self.assertEqual(extract_list(by_id[ident].get("authors")), authors)
        for meta in by_id.values():
            if meta["fcj_id"] in expected:
                for managing in ("Andrew Murphie", "Su Ballard", "Susan Ballard"):
                    self.assertNotIn(managing, extract_list(meta.get("authors")),
                                     f"{meta['fcj_id']} credits a managing editor")

    def test_a_declaration_never_overrides_a_recorded_author(self):
        """EDITORIAL_AUTHORS is applied only where the page records none. If a
        declared paper ever gains real citation metadata, this fails, so the
        declaration is removed instead of silently winning."""
        import resolve
        for ident in extract.EDITORIAL_AUTHORS:
            meta = next(m for m, _b, _p in self.papers.values()
                        if m["fcj_id"] == ident)
            source = os.path.join(resolve.STATIC_ROOT, meta["source_file"])
            if not os.path.isfile(source):
                self.skipTest("mirror not present")
            import markdown
            self.assertEqual(markdown.authors(inventory.read(source)), [],
                             f"{ident} now records its own authors")

    def test_every_paper_records_where_it_came_from(self):
        for slug, (meta, _body, _p) in self.papers.items():
            self.assertTrue(meta.get("source_url"), slug)
            self.assertTrue(meta.get("source_file"), slug)

    def test_no_body_still_contains_raw_html_except_tables(self):
        """Markdown that is half HTML is not reusable text.

        Tables are the one documented exception: 9 of them, passed through
        because a pipe table cannot express their colspans.
        """
        for slug, (_meta, body, _p) in self.papers.items():
            # A table is passed through whole, including whatever it contains:
            # FCJ-101 lays out its argument in a two-column table whose cells
            # hold numbered paragraphs, and stripping their markup would throw
            # away 20 citable paragraph numbers. The span is therefore the
            # documented exception, not just the table tags.
            # Innermost-first, repeatedly, because FCJ-101 nests a table in a
            # table. A single `<table.*?</table>` stops at the inner close and
            # leaves the outer table's contents looking like stray HTML.
            while re.search(r"(?is)<table\b", body):
                body, n = re.subn(
                    r"(?is)<table\b(?:(?!<table\b).)*?</table>", " ", body, count=1)
                if not n:
                    break
            # Markup inside a code span is markup the AUTHOR quoted — FCJ-127
            # prints XML in its argument. It is text, correctly fenced, so it
            # is not raw HTML and must not be counted as such.
            body = re.sub(r"`[^`\n]+`", "", body)
            tags = re.findall(r"</?[a-zA-Z][^>]*>", body)
            self.assertEqual(tags[:4], [], f"{slug} still contains HTML: {tags[:4]}")

    def test_paragraph_numbers_are_in_order_within_each_paper(self):
        for slug, (_meta, body, _p) in self.papers.items():
            numbers = [int(n) for n in re.findall(r"\{#para(\d+)\}", body)]
            self.assertEqual(numbers, sorted(numbers), f"{slug} numbers out of order")
            self.assertEqual(len(numbers), len(set(numbers)), f"{slug} duplicate numbers")

    def test_the_archive_carries_its_citation_numbers(self):
        """Was 17,000 when the numbers ran on through the notes, references and
        biographies. They now stop at the end of the main text — 5,335 of them
        were apparatus — so the floor measures the MAIN TEXT's numbering, which
        is what is actually citable.

        Both bounds matter. Too few means the apparatus cut is landing early
        and eating the argument; too many means it has stopped working.
        """
        total = sum(len(re.findall(r"\{#para\d+\}", body))
                    for _m, body, _p in self.papers.values())
        self.assertGreater(total, 11_500, "the apparatus cut is too greedy")
        self.assertLess(total, 14_000, "apparatus numbering has come back")

    def test_every_issue_lists_papers_that_exist(self):
        by_id = {meta["fcj_id"] for meta, _b, _p in self.papers.values()}
        for number, (meta, _body, _p) in self.issues.items():
            for ident in extract_list(meta.get("papers")):
                self.assertIn(ident, by_id, f"issue {number} lists missing {ident}")

    def test_every_link_in_the_body_is_relative_and_resolves_on_disk(self):
        """The archive promises text reusable WITHOUT the website.

        A root-relative `/media/…` resolves on the site and nowhere else: in a
        GitHub file view it points at the repository root rather than the file,
        and a single `.md` someone downloaded has no images at all. So links
        are relative to the file that uses them, and this walks all 416 of
        them from their own directory.
        """
        unresolved = []
        for sub, files in (("papers", self.papers), ("issues", self.issues)):
            base = os.path.join(CONTENT, sub)
            for slug, (_meta, body, _p) in files.items():
                for target in re.findall(r"\]\(([^)#]+?)(?:#[^)]*)?\)", body):
                    if target.startswith(("http", "mailto:", "#")) or not target.strip():
                        continue
                    self.assertFalse(target.startswith("/"),
                                     f"{slug}: {target} is root-relative")
                    if not os.path.exists(os.path.join(base, target)):
                        unresolved.append((slug, target))
        self.assertEqual(unresolved[:5], [], f"{len(unresolved)} broken targets")

    def test_front_matter_paths_are_relative_to_the_content_root(self):
        """Front matter is DATA read by tools, not Markdown rendered by a
        viewer, so those paths stay content-root-relative. Stated because the
        two conventions sit in one file and look inconsistent otherwise."""
        for slug, (meta, _body, _p) in self.papers.items():
            for key in ("pdf", "epub"):
                if meta.get(key):
                    value = str(meta[key])
                    self.assertFalse(value.startswith(("/", "../")), f"{slug} {key}")
                    self.assertTrue(os.path.isfile(os.path.join(CONTENT, value)),
                                    f"{slug} references missing {value}")

    def test_the_institutional_pages_are_extracted(self):
        """A journal's standing rests on showing who edits it, how it reviews
        and who preserves it. An archive of the articles alone demotes a
        peer-reviewed journal to a pile of PDFs."""
        pages = os.path.join(CONTENT, "pages")
        self.assertTrue(os.path.isdir(pages))
        got = {n[:-3] for n in os.listdir(pages) if n.endswith(".md")}
        self.assertEqual(got, {"about", "editorial-and-guidelines",
                               "publication-status"})

    def test_reading_theme_headers_does_not_import_theme_assets(self):
        """`wp-content/themes` is excluded from the archive, and reading a
        theme's files for any purpose must not become a route by which the old
        theme's CSS and images re-enter an archive that publishes the journal
        in its own format."""
        self.assertTrue(inventory.FURNITURE.match("wp-content/themes/x/y.css"))
        media = os.path.join(CONTENT, "media")
        for root, _dirs, files in os.walk(media):
            self.assertNotIn("themes", root.split(os.sep),
                             f"theme assets reached {root}")
            for name in files:
                self.assertNotEqual(name, "style.css", os.path.join(root, name))

    def test_journal_metadata_seeds_into_an_empty_directory(self):
        """Exercises the seeding PATH, not just the seeded file.

        `journal.md` is the one file in `content/` that is never regenerated,
        so on a built archive `write_journal` returns immediately and the seed
        is never touched. That is how a refactor deleted `JOURNAL_SEED` while
        leaving `write_journal` referencing it: the whole suite passed, and
        the archive would only have broken for the next person to build it
        from scratch. The fix is a test that takes the other branch.
        """
        with tempfile.TemporaryDirectory() as tmp:
            report = extract.ExtractReport()
            extract.write_journal(tmp, report)
            self.assertFalse(report.journal_kept, "should have seeded")
            path = os.path.join(tmp, "journal.md")
            self.assertTrue(os.path.isfile(path))
            with open(path, encoding="utf-8") as fh:
                meta, body = extract.parse_front_matter(fh.read())
            for key in ("title", "issn", "publisher", "licence",
                        "lockss_statement", "ceased"):
                self.assertTrue(meta.get(key), key)
            self.assertEqual(
                str(meta["lockss_statement"]),
                "LOCKSS system has permission to collect, preserve, and serve "
                "this open access Archival Unit.")
            self.assertIn("seeded once", body)

            # And the second call must keep what is there.
            again = extract.ExtractReport()
            extract.write_journal(tmp, again)
            self.assertTrue(again.journal_kept)

    def test_the_live_journal_file_is_hand_maintained(self):
        path = os.path.join(CONTENT, "journal.md")
        with open(path, encoding="utf-8") as fh:
            before = fh.read()
        report = extract.ExtractReport()
        extract.write_journal(CONTENT, report)
        self.assertTrue(report.journal_kept)
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)

    def test_paragraph_numbers_stop_at_the_end_of_the_main_text(self):
        """They ran on into the notes, references and biographies — 5,335 of
        17,796 of them, in 217 of 237 papers. In an offprint they are set in
        the margin, so a reference list arrived with a numbered rail beside it,
        implying a reference can be cited by paragraph. It cannot."""
        offenders = []
        for sub in ("papers", "issues"):
            for name in sorted(os.listdir(os.path.join(CONTENT, sub))):
                if not name.endswith(".md"):
                    continue
                with open(os.path.join(CONTENT, sub, name),
                          encoding="utf-8") as fh:
                    _meta, body = extract.parse_front_matter(fh.read())
                heads = list(extract.ANY_HEADING.finditer(body))
                cut = None
                for match in reversed(heads):
                    if not extract.APPARATUS_HEADING.match(
                            match.group(2).strip(" *_#")):
                        break
                    cut = match.start()
                if cut is not None and re.search(r"\{#para\d+\}", body[cut:]):
                    offenders.append(f"{sub}/{name}")
        self.assertEqual(offenders, [])

    def test_the_cut_is_the_trailing_run_not_the_first_apparatus_heading(self):
        """The guard that protects the citable unit. Ten papers have an
        apparatus heading BEFORE the end — `Notes` then `Appendix I`, or
        `Author's Biography` then `Journal Note`. Cutting at the first match
        would unnumber the rest of the article: destroying the citable unit
        for most of a paper to tidy up its reference list."""
        md = ("## Note\n\nan aside {#para2}\n\n"
              "## Discussion\n\nthe argument continues {#para3}\n\n"
              "## References\n\nSomebody (2001) {#para4}\n")
        out = extract.unnumber_apparatus(md)
        # The mid-text Note and everything after it, up to the trailing run,
        # keeps its numbers.
        self.assertIn("an aside {#para2}", out)
        self.assertIn("the argument continues {#para3}", out)
        # The trailing run loses them.
        self.assertIn("Somebody (2001)", out)
        self.assertNotIn("{#para4}", out)

    def test_the_main_text_keeps_its_numbers(self):
        """The failure mode of cutting too early is silent: the article still
        renders, it just stops being citable. So assert a FLOOR as well as the
        absence above."""
        total = 0
        for name in os.listdir(os.path.join(CONTENT, "papers")):
            if not name.endswith(".md"):
                continue
            with open(os.path.join(CONTENT, "papers", name),
                      encoding="utf-8") as fh:
                total += len(re.findall(r"\{#para\d+\}", fh.read()))
        self.assertGreater(total, 11_500, "the cut is landing too early")

    def test_a_paper_with_no_apparatus_is_untouched(self):
        md = "## Introduction\n\ntext {#para1}\n"
        self.assertEqual(extract.unnumber_apparatus(md), md)

    def test_the_curly_apostrophe_is_matched(self):
        """`Authors’ Biographies` with a curly apostrophe failed a pattern
        written for `Author's`. Because the cut is the trailing RUN, that one
        miss broke the walk and left `Notes` numbered in ten papers."""
        for heading in ("Authors’ Biographies", "Author’s Biography",
                        "Biographical Note", "Appendix I", "Thanks",
                        "Journal Note", "Works Cited", "Artworks"):
            self.assertTrue(extract.APPARATUS_HEADING.match(heading), heading)
        for heading in ("Introduction", "Conclusion", "Discussion",
                        "Note on Method", "References to Empire"):
            self.assertFalse(extract.APPARATUS_HEADING.match(heading), heading)

    def test_corrections_are_applied_and_recorded(self):
        """The archive's only departure from the crawled pages.

        An archive is citable because its text is the text that was published.
        The moment it corrects its source without saying so, a reader has no
        way to tell which is which — so every correction is declared, reasoned
        and written to `content/corrections.md` by the same list that applies
        it. One source of truth: there is no second copy to fall out of step.
        """
        with open(os.path.join(CONTENT, "pages",
                               "editorial-and-guidelines.md"),
                  encoding="utf-8") as fh:
            _meta, body = extract.parse_front_matter(fh.read())
        manager = body.split("## Journal Manager", 1)[1].split("\n## ", 1)[0]
        self.assertIn("Mat Wall-Smith", manager)
        self.assertNotIn("Andrew Murphie", manager)
        self.assertIn("Mat Wall-Smith (University of Wollongong)", body)
        self.assertNotIn("Mat Wall-Smith (Independent scholar", body)

        # Every correction must carry its reason in the declaration itself.
        # The archive publishes no note about them — the editors asked for
        # nothing to be added to the journal — so this list IS the record.
        for fix in extract.CORRECTIONS:
            self.assertTrue(fix["reason"], f"correction with no reason: {fix}")
            self.assertTrue(fix["section"], "a correction with no scope")

    def test_a_correction_cannot_reach_outside_its_section(self):
        """The scope is the whole safety argument. "Andrew Murphie" is also
        one of the five Journal Editors on the very page whose Journal Manager
        line is corrected; a page-wide replace would delete him from the
        editors, which is a different false claim."""
        editors = None
        with open(os.path.join(CONTENT, "pages",
                               "editorial-and-guidelines.md"),
                  encoding="utf-8") as fh:
            _meta, body = extract.parse_front_matter(fh.read())
        editors = body.split("## Journal Editors", 1)[1].split("\n## ", 1)[0]
        self.assertIn("Andrew Murphie (UNSW Sydney)", editors,
                      "the correction leaked out of its section")
        # And directly, on a fixture, so the guarantee does not depend on the
        # current shape of one real page.
        md = ("## Journal Editors\n\nAndrew Murphie\n\n"
              "## Journal Manager\n\nAndrew Murphie\n\n"
              "## Editorial Board\n\nAndrew Murphie\n")
        out = extract.apply_corrections("editorial-and-guidelines", md)
        self.assertEqual(out.count("Mat Wall-Smith"), 1)
        self.assertEqual(out.count("Andrew Murphie"), 2)

    def test_a_correction_for_another_page_does_nothing(self):
        md = "## Journal Manager\n\nAndrew Murphie\n"
        self.assertEqual(extract.apply_corrections("about", md), md)

    def test_the_old_navigation_menu_is_gone(self):
        """WordPress put the "Page Navigation:" label and the menu itself in
        separate <p> elements, so removing the label left the links:

            :: editorial board and management
            :: editorial policy

        They were in-page anchors; the archive emits no `<a name>` targets, and
        every section they point at is now a real heading.
        """
        for name in os.listdir(os.path.join(CONTENT, "pages")):
            if not name.endswith(".md"):
                continue
            with open(os.path.join(CONTENT, "pages", name),
                      encoding="utf-8") as fh:
                _meta, body = extract.parse_front_matter(fh.read())
            for line in body.splitlines():
                self.assertFalse(re.match(r"^\s*::\s+\S", line),
                                 f"{name}: menu item left behind: {line!r}")
            self.assertNotIn("Page Navigation", body, name)

    def test_authored_double_colons_survive(self):
        """The rule must not be "delete `::`". The About page uses it as an
        inline separator inside its list of topics — mid-line, never at the
        start of one — and `::: embed` is a fence in the Markdown dialect.
        Both are content."""
        with open(os.path.join(CONTENT, "pages", "about.md"),
                  encoding="utf-8") as fh:
            about = fh.read()
        self.assertIn("media innovation, and their critique :: national", about)
        fences = 0
        for name in os.listdir(os.path.join(CONTENT, "papers")):
            if not name.endswith(".md"):
                continue
            with open(os.path.join(CONTENT, "papers", name),
                      encoding="utf-8") as fh:
                fences += "::: embed" in fh.read()
        self.assertGreater(fences, 0, "embed fences destroyed")

    def test_theme_icons_do_not_reach_the_archive(self):
        """The regression this caught: `THEME_IMAGE` was written against the
        root-relative `/media/…` the rewriter used to emit. When the archive
        moved to relative paths it silently stopped matching and the old
        theme's PDF and ePub icons came back on issues 20, 28 and 29.

        So the pattern is asserted against BOTH shapes, not just the one in
        use today — that is the whole point of the failure.
        """
        self.assertTrue(extract.THEME_IMAGE.search(
            "![](../media/x.org/wp-content/themes/fcjissue19/PDFicon.gif)"))
        self.assertTrue(extract.THEME_IMAGE.search(
            "![](/media/x.org/wp-content/themes/fcjissue19/PDFicon.gif)"))
        for sub in ("papers", "issues"):
            for name in os.listdir(os.path.join(CONTENT, sub)):
                if not name.endswith(".md"):
                    continue
                with open(os.path.join(CONTENT, sub, name),
                          encoding="utf-8") as fh:
                    self.assertNotIn("wp-content/themes", fh.read(),
                                     f"{sub}/{name} keeps theme chrome")

    def test_stale_media_is_pruned_but_only_above_the_floor(self):
        """`_prune` now deletes from the tree holding every image, PDF and
        ePub in the archive, driven by a set its caller assembles. If that set
        comes back short the honest outcome is to delete NOTHING: the mirror is
        read-only and a wrong deletion is recoverable only by a full
        re-extract."""
        self.assertGreaterEqual(extract.MEDIA_FLOOR, 100)
        with tempfile.TemporaryDirectory() as tmp:
            media = os.path.join(tmp, "media")
            os.makedirs(media)
            victim = os.path.join(media, "orphan.gif")
            with open(victim, "w") as fh:
                fh.write("x")
            # A short set must not trigger deletion.
            extract._prune(tmp, set(), {os.path.join(media, "kept.gif")})
            self.assertTrue(os.path.isfile(victim), "deleted below the floor")
            # A plausible set must.
            plausible = {os.path.join(media, f"k{i}.gif")
                         for i in range(extract.MEDIA_FLOOR)}
            removed = extract._prune(tmp, set(), plausible)
            self.assertFalse(os.path.isfile(victim))
            self.assertIn("media/orphan.gif", removed)

    def test_the_banners_survived_the_theme_exclusion(self):
        """The blast radius of getting `in_code_theme` wrong. The banners live
        INSIDE `wp-content/themes/fcsharedimg/`."""
        banners = os.path.join(CONTENT, "media", "banners")
        self.assertEqual(
            len([n for n in os.listdir(banners) if not n.startswith(".")]), 13)

    def test_page_headings_carry_no_styling_artefacts(self):
        """The mirror writes `#### **editor**` — bold inside the heading, at a
        level that was a subsection of a longer page. Both are presentation,
        not structure; a page of its own starts at `##`."""
        for name in os.listdir(os.path.join(CONTENT, "pages")):
            if not name.endswith(".md"):
                continue
            with open(os.path.join(CONTENT, "pages", name),
                      encoding="utf-8") as fh:
                _meta, body = extract.parse_front_matter(fh.read())
            for hashes, text in re.findall(r"(?m)^(#{1,6}) (.+)$", body):
                self.assertNotIn("**", text, f"{name}: bold in heading {text!r}")
                self.assertGreaterEqual(len(hashes), 2, f"{name}: {text!r}")
                self.assertLessEqual(len(hashes), 3, f"{name}: {text!r}")

    def test_the_guidelines_page_keeps_its_substance(self):
        """1,743 words in the source, holding the board, the review policy and
        the submission guidelines. Checked on substance, not on the file
        existing — an empty file would pass that."""
        path = os.path.join(CONTENT, "pages", "editorial-and-guidelines.md")
        with open(path, encoding="utf-8") as fh:
            _meta, body = extract.parse_front_matter(fh.read())
        self.assertGreater(len(body.split()), 1600)
        headings = re.findall(r"(?m)^#{2,6} (.+)$", body)
        for expected in ("Journal Editors", "Editorial Board"):
            self.assertIn(expected, headings, f"{expected} heading lost")
        # The people are the point.
        for name in ("Su Ballard", "Andrew Murphie"):
            self.assertIn(name, body, f"{name} missing from the board")

    def test_the_page_list_is_explicit_not_a_directory_scan(self):
        """The same apex directory holds `write-for-us-sponsored-posts`, which
        is an artefact of the compromise, plus hundreds of category pages."""
        sources = {p[0] for p in extract.INSTITUTIONAL_PAGES}
        self.assertNotIn("write-for-us-sponsored-posts", sources)
        got = {n[:-3] for n in os.listdir(os.path.join(CONTENT, "pages"))}
        self.assertNotIn("write-for-us-sponsored-posts", got)

    def test_journal_metadata_is_seeded_and_then_left_alone(self):
        """`journal.md` is the one file in `content/` that is hand-maintained:
        it is what another journal edits to adopt this archive, so a re-extract
        must not overwrite it."""
        path = os.path.join(CONTENT, "journal.md")
        self.assertTrue(os.path.isfile(path))
        with open(path, encoding="utf-8") as fh:
            meta, _ = extract.parse_front_matter(fh.read())
        for key in ("title", "issn", "publisher", "licence", "lockss_statement"):
            self.assertTrue(meta.get(key), key)
        with open(path, encoding="utf-8") as fh:
            before = fh.read()
        report = extract.ExtractReport()
        extract.write_journal(CONTENT, report)
        self.assertTrue(report.journal_kept)
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)

    def test_the_lockss_statement_is_verbatim(self):
        """A LOCKSS crawler looks for this exact sentence. Paraphrasing it, or
        leaving it in a `title` attribute as the mirror did, makes it inert."""
        with open(os.path.join(CONTENT, "journal.md"), encoding="utf-8") as fh:
            meta, _ = extract.parse_front_matter(fh.read())
        self.assertEqual(
            str(meta["lockss_statement"]),
            "LOCKSS system has permission to collect, preserve, and serve "
            "this open access Archival Unit.")

    def test_readme_explains_the_paragraph_numbers(self):
        with open(os.path.join(CONTENT, "README.md"), encoding="utf-8") as fh:
            readme = fh.read()
        self.assertIn("para76", readme)
        self.assertIn("sed", readme, "the README must give the strip command")

    def test_body_is_renderable(self):
        """Every file in the archive must render, or the site has a hole."""
        for slug, (_meta, body, _p) in self.papers.items():
            html = markdown.render(body)
            self.assertNotIn("{#para", html, slug)


def extract_list(value):
    if not value:
        return []
    return value if isinstance(value, list) else [value]


# A list item whose text begins with its own dash: `- – informational logics`.
LIST_DASH = re.compile(r"(?m)^\s*[-*+]\s+[–—-]\s+")


@needs_content
class TestTheDoubledBulletIsOnlyStrippedFromPages(unittest.TestCase):
    """The old theme showed no list marker, so a literal en-dash inside each
    `<li>` WAS the bullet. Rendered here it doubles up.

    Both halves of this matter. Stripping it from the institutional pages is
    the fix; NOT stripping it from the papers is the constraint, because
    FCJ-134 and FCJ-119 open list items with the same dash to introduce
    propositions quoted from a cited framework. That is the authors' prose
    under CC BY-NC-ND. The rule therefore lives in `structure_page`, which only
    pages go through, and these two tests are what would catch it being moved
    into the shared converter.
    """

    def _read(self, path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def test_no_institutional_page_has_a_doubled_bullet(self):
        pages = os.path.join(CONTENT, "pages")
        for name in sorted(os.listdir(pages)):
            if not name.endswith(".md"):
                continue
            found = LIST_DASH.findall(self._read(os.path.join(pages, name)))
            self.assertEqual(found, [], f"pages/{name} still doubles its bullets")

    def test_the_papers_keep_the_dashes_their_authors_wrote(self):
        kept = 0
        for name in sorted(os.listdir(os.path.join(CONTENT, "papers"))):
            if not name.startswith(("fcj-134", "fcj-119")):
                continue
            body = self._read(os.path.join(CONTENT, "papers", name))
            kept += len(LIST_DASH.findall(body))
        self.assertGreater(kept, 20,
                           "a page-cleaning rule has reached into the papers "
                           "and edited an author's prose")

    def test_a_dash_inside_an_item_is_not_touched(self):
        """`(1 January 2005 – 31 December 2010)` is a date range, not a bullet.
        The rule anchors to the start of the item for this reason."""
        about = self._read(os.path.join(CONTENT, "pages", "about.md"))
        self.assertIn("(1 January 2005 – 31 December 2010)", about)


if __name__ == "__main__":
    unittest.main()
