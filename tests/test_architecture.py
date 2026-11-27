#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""The tool-separation boundary, enforced.

Governed by docs/architecture.md, "The repository is the integration point, not
an application".

Mat's direction: the capabilities a platform like OJS bundles into one system
hang off the git structure as SEPARATE TOOLS. The repository is what they
integrate through, not an application they live inside.

That is easy to write down and easy to erode one import at a time, which is
exactly what happened here: the banner feature had `generate.py` reaching into
`fcj-static` to find a header image, breaking the one boundary the whole design
rests on, and nothing noticed. So the boundary is a test.

These tests read source files rather than behaviour, which is unusual and
deliberate: the property being protected is structural. A behavioural test
cannot see the difference between a tool that stands alone and one that happens
to work today.
"""
from __future__ import annotations

import ast
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")

# Which modules each tool is allowed to import from this project.
#
# `markdown` and `resolve` are shared LIBRARIES — the dialect and the mirror's
# URL conventions — not tools, so depending on them is not coupling. `extract`
# is imported by others only for the format contract (`parse_front_matter`,
# `paper_dir`), which is the published interface rather than an internal.
ALLOWED = {
    "resolve.py": set(),
    "markdown.py": set(),
    "inventory.py": {"resolve"},
    "extract.py": {"inventory", "markdown", "resolve"},
    "redirects.py": {"extract", "inventory", "resolve"},
    "audit_spam.py": {"inventory", "resolve"},
    # Nothing, deliberately. An audit that shared the extractor's parser could
    # not see a defect in that parser, and it must stay independently
    # deletable like every other tool here.
    "audit_content.py": set(),
    # The only tool that touches the network, and the only writer of
    # `recovered/`. It reads `content/` to learn what is referenced and needs
    # nothing else. `extract.py` must never import it, or a build would stop
    # being reproducible offline.
    "recover.py": set(),
    "pdfs.py": {"extract"},
    "generate.py": {"extract", "markdown"},
}

# Only these may read the crawled mirror. Everything else works from `content/`.
MAY_READ_MIRROR = {"resolve.py", "inventory.py", "extract.py", "redirects.py",
                   "audit_spam.py"}


def local_imports(path: str) -> set[str]:
    """Project modules a file imports, including inside functions."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), path)
    here = {f[:-3] for f in os.listdir(BUILD) if f.endswith(".py")}
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module.split(".")[0])
    return found & here


def code_without_comments(path: str) -> str:
    """Source with comments and docstrings removed.

    A module may NAME the mirror in a comment explaining why it must not read
    it — `generate.py` does exactly that — so the check has to look at code.
    """
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source, path)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                docstrings.add(doc)
    lines = [ln.split("#", 1)[0] if not ln.strip().startswith("#") else ""
             for ln in source.splitlines()]
    stripped = "\n".join(lines)
    for doc in docstrings:
        stripped = stripped.replace(doc, "")
    return stripped


class TestToolSeparation(unittest.TestCase):
    def test_every_build_module_is_accounted_for(self):
        """A new tool must declare its dependencies here, deliberately."""
        modules = {f for f in os.listdir(BUILD)
                   if f.endswith(".py") and not f.startswith("_")}
        self.assertEqual(modules, set(ALLOWED),
                         "a build module was added or removed without updating "
                         "ALLOWED — declare what it may depend on")

    def test_no_tool_imports_more_than_it_is_allowed_to(self):
        for name, allowed in ALLOWED.items():
            actual = local_imports(os.path.join(BUILD, name))
            self.assertLessEqual(
                actual, allowed,
                f"{name} imports {sorted(actual - allowed)}; either it is doing "
                f"another tool's job, or ALLOWED needs a reasoned change")

    def test_the_render_stage_never_reads_the_mirror(self):
        """The boundary the whole design rests on.

        `generate.py` renders from `content/` alone, so the text people
        download is the text the site shows. A single read of `fcj-static`
        from here reintroduces the drift this architecture exists to prevent —
        and that is not hypothetical: the banner feature did it.
        """
        for name in sorted(set(ALLOWED) - MAY_READ_MIRROR):
            code = code_without_comments(os.path.join(BUILD, name))
            for forbidden in ("fcj-static", "STATIC_ROOT", "SOURCE_ROOT",
                              "fcj-crawl", "fcj-kit"):
                self.assertNotIn(forbidden, code, f"{name} reaches into the mirror")

    def test_no_build_module_hardcodes_a_machine_specific_path(self):
        """Input locations are derived, never written out.

        `resolve.py` held the mirror's absolute path until the project was
        consolidated under `~/webdev/fibreculture/`. That made moving a
        directory a code change, and the failure was invisible: the
        mirror-dependent tests are guarded by
        `skipUnless(os.path.isdir(resolve.STATIC_ROOT))`, so a stale path drops
        52 of 240 tests and the run still prints OK.

        Deriving every input location from `__file__` means the project
        relocates as a unit. This test is what stops an absolute path returning
        and taking that property with it — see `resolve.SOURCE_ROOT` and
        docs/architecture.md ("Inputs").
        """
        for name in sorted(ALLOWED):
            code = code_without_comments(os.path.join(BUILD, name))
            for absolute in ("/Users/", "/home/", "expanduser"):
                self.assertNotIn(
                    absolute, code,
                    f"{name} hardcodes a machine-specific path; derive it from "
                    f"__file__ as resolve.SOURCE_ROOT does")

    def test_no_tool_imports_another_tool_that_produces_an_artefact(self):
        """Each capability must be deletable.

        Removing `pdfs.py` should cost the offprints and nothing else. If
        `generate.py` imported it, deleting it would break the site.
        """
        producers = {"pdfs", "redirects", "audit_spam", "generate"}
        for name in ALLOWED:
            imported = local_imports(os.path.join(BUILD, name))
            overlap = imported & producers - {name[:-3]}
            self.assertEqual(overlap, set(),
                             f"{name} depends on the tool {sorted(overlap)}, "
                             f"which cannot then be removed independently")

    def test_each_tool_runs_on_its_own(self):
        """Every tool is an executable, not a mode of an application."""
        for name in ALLOWED:
            with open(os.path.join(BUILD, name), encoding="utf-8") as fh:
                source = fh.read()
            if name in ("resolve.py", "markdown.py"):
                continue          # shared libraries, not tools
            self.assertIn('if __name__ == "__main__":', source,
                          f"{name} cannot be run on its own")


class TestTheFormatIsAContract(unittest.TestCase):
    """The front matter is the interface separate tools integrate through, so
    the keys are specified in the architecture doc, not left to whatever
    `extract.py` happens to emit."""

    REQUIRED = ("fcj_id", "title", "issue", "source_url", "source_file",
                "journal", "issn", "licence", "doi", "abstract", "authors",
                "pdf", "epub")

    @staticmethod
    def _spec() -> str:
        with open(os.path.join(ROOT, "docs", "architecture.md"),
                  encoding="utf-8") as fh:
            return fh.read()

    def test_the_spec_documents_every_key_extract_writes(self):
        spec = self._spec()
        for key in self.REQUIRED:
            self.assertIn(f"`{key}`", spec,
                          f"front-matter key {key} is written but not specified")

    def test_the_spec_documents_the_issue_keys_too(self):
        spec = self._spec()
        for key in ("editors", "full_issue_pdf", "full_issue_epub", "banner"):
            self.assertIn(f"`{key}`", spec,
                          f"issue front-matter key {key} is written but not specified")

    def test_the_spec_states_that_a_file_must_stand_alone(self):
        self.assertIn("stand alone", self._spec())


class TestAttributionTravelsWithTheFile(unittest.TestCase):
    """Attribution has to be IN each file, not only in LICENSE at the root.

    Apache-2.0 §4(c) requires attribution notices to be retained in derivative
    works, but a licence file at the repository root only travels with a clone.
    This architecture guarantees single files get copied instead: every tool is
    specified to be independently removable, so `pdfs.py` or `markdown.py` will
    be lifted out on its own. A file with no notice in it arrives anonymous.
    """

    NOTICE = "created by Mathew Wall-Smith"

    def _files(self):
        import glob
        for pattern in ("build/*.py", "tests/*.py"):
            yield from sorted(glob.glob(os.path.join(ROOT, pattern)))
        # Not `.scripts/check-docs.sh`: it is local development scaffolding,
        # untracked, so it does not exist in a clone and this would error there.
        for extra in ("assets/style.css", "assets/offprint.typ"):
            yield os.path.join(ROOT, extra)

    def test_every_tool_and_design_file_carries_the_notice(self):
        missing = []
        for path in self._files():
            with open(path, encoding="utf-8") as fh:
                if self.NOTICE not in fh.read():
                    missing.append(os.path.relpath(path, ROOT))
        self.assertEqual(missing, [],
                         "these files would arrive anonymous if copied alone")

    def test_the_notice_sits_after_the_shebang_not_before_it(self):
        """A notice above `#!` stops the file being executable."""
        for path in self._files():
            with open(path, encoding="utf-8") as fh:
                first = fh.readline()
            if first.startswith("#!") or not first.startswith(("#", "/")):
                continue
            self.assertNotIn("#!", first,
                             f"{os.path.relpath(path, ROOT)}: notice precedes "
                             f"the shebang")

    def test_the_root_carries_the_licence_and_the_notice_file(self):
        """NOTICE is the §4(d) mechanism: its contents must be reproduced in
        derivative works, which is what carries the attribution forward rather
        than merely permitting it."""
        for name in ("LICENSE", "NOTICE", "LICENCE.md"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, name)),
                            f"{name} is missing from the repository root")
        with open(os.path.join(ROOT, "NOTICE"), encoding="utf-8") as fh:
            notice = fh.read()
        self.assertIn(self.NOTICE, notice)
        # The articles are not the archive author's to license.
        self.assertIn("retain copyright", notice)


if __name__ == "__main__":
    unittest.main()
