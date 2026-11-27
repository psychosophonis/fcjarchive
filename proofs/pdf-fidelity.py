#!/usr/bin/env python3
"""PROBE: can pandoc turn our Markdown into a faithful academic PDF?

Run: python3 proofs/pdf-fidelity.py

THE IDEA AT RISK
    128 of the archive's 237 papers have no publisher PDF, and 121 of those are
    in issues 1-16. An author with a 2005 paper has nothing to deposit in their
    institutional repository. The proposal is to render offprints with pandoc.
    That only works if the conversion is faithful: a PDF that quietly drops the
    reference list, the figure captions, or the paragraph numbers is worse than
    no PDF, because it will be deposited and cited as though it were complete.

ALREADY HALF-FALSIFIED BEFORE THIS PROBE WAS WRITTEN
    Feeding a real paper to pandoc as-is leaks 48 literal `{#para76}` markers
    into the output: pandoc's attribute syntax applies to headings, spans and
    divs, not to bare paragraphs. So the dialect MUST be pre-processed. The
    question this probe answers is what ELSE breaks.

FOUR ATTEMPTS TO KILL IT:

  1. DOES ANY DIALECT SYNTAX REACH THE READER — `{#paraN}`, `::: embed`, raw
     HTML tables, code spans?
  2. DOES THE APPARATUS SURVIVE — italics, blockquotes, figures WITH captions,
     the notes section, the reference list?
  3. DO THE PARAGRAPH CITATION NUMBERS SURVIVE in a form distinguishable from
     footnote markers? Both are `[n]` in this corpus.
  4. IS THE TEXT COMPLETE? Render and extract, and compare word counts.

Attempts 1-3 need no PDF engine: they read the typst markup pandoc emits.
Attempt 4 needs one, and is SKIPPED WITH A MESSAGE rather than passed silently
when none is installed.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "build"))

import extract  # noqa: E402
import markdown  # noqa: E402

CONTENT = os.path.join(HERE, "content")
ENGINES = ("typst", "xelatex", "lualatex", "pdflatex", "tectonic", "weasyprint",
           "wkhtmltopdf", "context")

# One paper per awkward feature, as measured over the whole corpus.
HARD = ["fcj-001", "fcj-047", "fcj-101", "fcj-113", "fcj-120", "fcj-160", "fcj-218"]


def find_engine() -> str | None:
    for name in ENGINES:
        if shutil.which(name):
            return name
    return None


# --------------------------------------------------------------------------
# a minimal pre-processor: tests the principle, not the implementation


PARA_MARK = re.compile(r"[ \t]*\{#para(\d+)\}")


def preprocess_full(body: str) -> str:
    """Make the dialect pandoc-safe, LINE BY LINE.

    The first version of this worked block by block and took only the marker at
    the end of each block. That lost six paragraph numbers in FCJ-047, whose
    quoted passages hold five numbered paragraphs inside one blockquote — each
    its own `> ` line with its own marker. Paragraphs are single lines in this
    dialect, so the line is the right unit.

    The number moves to the FRONT, where the journal printed it, and carries a
    pilcrow: paragraph numbers and footnote markers are both bare `[n]` in this
    corpus, and in a PDF there is no hover or colour to tell them apart.
    """
    lines: list[str] = []
    for line in body.split("\n"):
        marks = PARA_MARK.findall(line)
        if marks:
            line = PARA_MARK.sub("", line)
            quote = re.match(r"^\s*>\s*", line)
            prefix = quote.group(0) if quote else ""
            rest = line[len(prefix):].lstrip()
            if rest:
                line = f"{prefix}[¶{marks[0]}]{{.paranum}} {rest}"
            else:
                # a numbered paragraph with no text: the theme numbered an
                # empty paragraph. Nothing to mark, nothing citable.
                line = prefix.rstrip()
        lines.append(line)
    body = "\n".join(lines)

    body = re.sub(
        r"(?m)^::: embed\n(.*?)\n:::$",
        lambda m: f"> **Embedded media, not hosted by this archive:** <{m.group(1)}>",
        body)
    return body


def html_tables_to_markdown(body: str) -> str:
    """Convert raw HTML tables with pandoc itself.

    Pandoc's typst writer drops an HTML table's structure and emits its cells
    as loose text — `cell one cell two` with no rows. Round-tripping the table
    through pandoc's HTML reader first keeps it a table.
    """
    def one(m: re.Match[str]) -> str:
        try:
            result = subprocess.run(
                ["pandoc", "-f", "html", "-t", "markdown"],
                input=m.group(0), capture_output=True, text=True, timeout=60)
            return "\n\n" + result.stdout.strip() + "\n\n" if result.returncode == 0 \
                else m.group(0)
        except (OSError, subprocess.SubprocessError):
            return m.group(0)

    # Balanced, not `<table.*?</table>`: FCJ-101 nests a table inside a table,
    # and the non-greedy form hands pandoc a fragment missing its closing tags.
    out: list[str] = []
    pos = 0
    while True:
        start = re.compile(r"(?i)<table\b").search(body, pos)
        if not start:
            out.append(body[pos:])
            return "".join(out)
        out.append(body[pos:start.start()])
        depth, end = 0, None
        for tag in re.finditer(r"(?i)<(/?)table\b[^>]*>", body[start.start():]):
            depth += -1 if tag.group(1) else 1
            if depth == 0:
                end = start.start() + tag.end()
                break
        end = end or len(body)

        class _M:
            def group(self, _n=0):
                return body[start.start():end]

        out.append(one(_M()))
        pos = end


def to_typst(body: str) -> str:
    result = subprocess.run(
        ["pandoc", "-f", "markdown+raw_html", "-t", "typst"],
        input=body, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise SystemExit(f"pandoc failed: {result.stderr[:400]}")
    return result.stdout


def words(text: str) -> list[str]:
    return [w for w in re.findall(r"[\w’'-]+", text.lower()) if w.strip("-'’")]


def load(slug_prefix: str) -> tuple[dict, str, str]:
    for name in sorted(os.listdir(os.path.join(CONTENT, "papers"))):
        if name.startswith(slug_prefix):
            path = os.path.join(CONTENT, "papers", name)
            with open(path, encoding="utf-8") as fh:
                meta, body = extract.parse_front_matter(fh.read())
            return meta, body, name[:-3]
    raise SystemExit(f"no paper matching {slug_prefix}")


def main() -> int:
    print(__doc__.split("FOUR ATTEMPTS")[0].strip())
    print("=" * 72)
    if not shutil.which("pandoc"):
        print("pandoc is not installed; nothing to probe.")
        return 1
    engine = find_engine()
    print(f"pandoc: {subprocess.run(['pandoc', '--version'], capture_output=True, text=True).stdout.splitlines()[0]}")
    print(f"pdf engine: {engine or 'NONE INSTALLED'}\n")

    fatal: list[str] = []

    # ---- attempts 1, 2, 3
    print("ATTEMPT 1/2/3 — dialect leaks and apparatus survival, per paper")
    print(f"  {'paper':<10}{'leaks':>7}{'¶nums':>7}{'emph':>6}{'figs':>6}"
          f"{'caps':>6}{'quote':>7}{'refs':>6}{'tables':>8}")
    for prefix in HARD:
        meta, body, slug = load(prefix)
        # Tables FIRST. Pandoc's HTML reader turns the `<p id="para11">` inside
        # a parked table back into `{#para11}` markdown, so pre-processing
        # before the table conversion leaves those markers to reach the reader.
        pre = preprocess_full(html_tables_to_markdown(body))
        typst = to_typst(pre)

        leaks = (len(re.findall(r"\{\\?#para", typst))
                 + typst.count("::: embed")
                 + len(re.findall(r"(?m)^#{2,6} ", typst)))
        paranums = len(re.findall(r"¶\d+", typst))
        expected_nums = len(re.findall(r"\{#para\d+\}", body))
        emph = typst.count("#emph[")
        figs = typst.count("#figure(")
        caps = typst.count("caption:")
        quotes = typst.count("#quote(")
        refs = 1 if re.search(r"(?mi)^==+ (references|bibliography)", typst) else 0
        tables = typst.count("#table(")
        md_tables = len(re.findall(r"(?is)<table\b", body))

        flag = "" if paranums >= expected_nums else f"  LOST {expected_nums - paranums}"
        print(f"  {prefix:<10}{leaks:>7}{paranums:>7}{emph:>6}{figs:>6}"
              f"{caps:>6}{quotes:>7}{refs:>6}{tables:>4}/{md_tables:<3}{flag}")
        if leaks:
            fatal.append(f"{slug}: {leaks} dialect leaks reach the reader")
        if paranums < expected_nums:
            fatal.append(f"{slug}: {expected_nums - paranums} paragraph numbers lost")
        if md_tables and not tables:
            fatal.append(f"{slug}: {md_tables} table(s) lost their structure")
    print()

    # ---- attempt 4
    print("ATTEMPT 4 — render, extract, compare word counts")
    if not engine:
        print("  SKIPPED: no PDF engine installed, so this probe cannot run.")
        print("  `brew install typst` enables it. Until then the completeness")
        print("  of the rendered PDF is UNPROVEN, and must not be assumed.")
    elif not shutil.which("pdftotext"):
        print("  SKIPPED: pdftotext not available to read the result back.")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            for prefix in HARD:
                meta, body, slug = load(prefix)
                pre = html_tables_to_markdown(preprocess_full(body))
                pdf = os.path.join(tmp, slug + ".pdf")
                run = subprocess.run(
                    ["pandoc", "-f", "markdown+raw_html", "--pdf-engine", engine,
                     "-o", pdf, "-"],
                    input=pre, capture_output=True, text=True, timeout=300)
                if run.returncode != 0:
                    print(f"  {prefix:<10}RENDER FAILED: {run.stderr.strip()[:140]}")
                    fatal.append(f"{slug}: render failed")
                    continue
                txt = subprocess.run(["pdftotext", pdf, "-"], capture_output=True,
                                     text=True, timeout=120).stdout
                md_words = Counter(words(markdown.strip_paragraph_numbers(pre)))
                pdf_words = Counter(words(txt))
                lost = sum((md_words - pdf_words).values())
                total = sum(md_words.values())
                pct = 100 * (1 - lost / total) if total else 0
                print(f"  {prefix:<10}{total:>7} words, {lost:>4} missing "
                      f"({pct:.1f}% retained), {os.path.getsize(pdf) / 1024:.0f} KB")
                if pct < 99:
                    fatal.append(f"{slug}: only {pct:.1f}% of words in the PDF")
    print()

    print("=" * 72)
    if fatal:
        print("IDEA DIED:")
        for item in fatal:
            print(f"  {item}")
        return 1
    print("IDEA SURVIVED (for the attempts that could run).")
    print("  The dialect must be pre-processed before pandoc sees it:")
    print("    - `{#paraN}` becomes a pilcrow mark at the start of the")
    print("      paragraph, so it cannot be confused with a `[n]` note marker;")
    print("    - `::: embed` becomes prose, or the reader is told nothing;")
    print("    - raw HTML tables are round-tripped through pandoc's HTML")
    print("      reader, or the typst writer emits their cells as loose text.")
    if not engine:
        print("  COMPLETENESS OF THE RENDERED PDF IS STILL UNPROVEN: no engine.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
