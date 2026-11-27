#!/usr/bin/env python3
# Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
"""Render archival offprints for papers with no publisher PDF.

Governed by docs/architecture.md ("Offprints").

128 of the archive's 237 papers have no PDF, and 121 of those are in issues
1-16 (2003-2010). An author with a 2005 paper currently has nothing to deposit
in their institutional repository. This renders one.

WHAT THIS IS NOT

For issues 1-16 the HTML **is** the version of record. A generated offprint
that looks like the published article would manufacture a second citable object
for the same paper, so every PDF carries a provenance colophon saying what it
is, and none is given a DOI of its own. That requirement is the reason this
module exists rather than a one-line pandoc invocation.

STYLE

The layout follows the journal's own later PDFs (issues 17-30, produced with
Asciidoctor PDF in 2017), measured from `FCJ-218PaulaBialski.pdf`: A4, single
column, Open Sans, `FCJ-nnn ` before the title, a one-line byline,
`Abstract:` bold inline, a `doi:` line, unnumbered bold headings, references as
a bulleted hanging-indent list. See `assets/offprint.typ`.

One departure, deliberate: those PDFs carry no paragraph numbers, but for
issues 1-16 the numbered HTML was the only published form, so citations to
those papers cite paragraphs. Dropping the numbers would make the offprint
unable to support the citations this archive exists to protect, so they go in
the outer margin in small grey type.

THE DIALECT MUST BE PRE-PROCESSED

`proofs/pdf-fidelity.py` established this, and the first version of it failed:
pandoc leaks 48 literal `{#para76}` markers into the output of a single paper,
because its attribute syntax applies to headings, spans and divs and not to
bare paragraphs. The probe also found that raw HTML tables lose their structure
in the typst writer unless round-tripped through pandoc's HTML reader first,
and that the table conversion must run BEFORE the paragraph pass — pandoc's
HTML reader turns a table's `<p id="para11">` back into `{#para11}`.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field

import extract

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(HERE, "content")
ASSETS = os.path.join(HERE, "assets")
TEMPLATE = os.path.join(ASSETS, "offprint.typ")
FONT_DIR = os.path.join(ASSETS, "pdf-fonts")
OUT_SUBDIR = "offprints"

# In preference order. typst is the intended engine: pandoc 3.x supports it
# natively, it is a single ~30 MB binary, and it needs no TeX tree.
ENGINES = ("typst", "xelatex", "lualatex", "tectonic", "pdflatex", "weasyprint")

PARA_MARK = re.compile(r"[ \t]*\{#para(\d+)\}")
EMBED = re.compile(r"(?m)^::: embed\n(.*?)\n:::$")
TABLE_OPEN = re.compile(r"(?i)<table\b")
TABLE_TAG = re.compile(r"(?i)<(/?)table\b[^>]*>")


@dataclass
class PdfReport:
    rendered: list[str] = field(default_factory=list)
    skipped_has_pdf: list[str] = field(default_factory=list)
    skipped_no_author: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    engine: str | None = None
    bytes_written: int = 0


def find_engine() -> str | None:
    for name in ENGINES:
        if shutil.which(name):
            return name
    return None


# --------------------------------------------------------------------------
# pre-processing


def html_tables_to_markdown(body: str) -> str:
    """Convert raw HTML tables to typst ONCE, and splice them as a raw block.

    The typst writer emits an HTML table's cells as loose text — `cell one cell
    two` with no rows — so the table has to be read as HTML. The obvious route,
    HTML -> markdown -> splice, does not work: pandoc's own markdown for
    FCJ-101's table is 95,000 characters of grid table, and re-reading it
    inside the paper takes longer than 50 seconds. Measured, after it hung a
    test run.

    So the table is converted HTML -> typst directly and wrapped in a
    ```{=typst} raw block, which pandoc passes through untouched. One
    conversion, no re-parse: 0.5s instead of never finishing.

    Matched by BALANCING the tags: FCJ-101 nests a table inside a table, and
    `<table.*?</table>` stops at the inner close, handing pandoc a fragment
    missing its own closing tags.
    """
    out: list[str] = []
    pos = 0
    while True:
        start = TABLE_OPEN.search(body, pos)
        if not start:
            out.append(body[pos:])
            return "".join(out)
        out.append(body[pos:start.start()])
        depth, end = 0, None
        for tag in TABLE_TAG.finditer(body, start.start()):
            depth += -1 if tag.group(1) else 1
            if depth == 0:
                end = tag.end()
                break
        end = end or len(body)
        html = body[start.start():end]
        try:
            run = subprocess.run(["pandoc", "-f", "html", "-t", "typst"],
                                 input=html, capture_output=True, text=True,
                                 timeout=120)
            if run.returncode == 0 and run.stdout.strip():
                out.append("\n\n```{=typst}\n"
                           + sanitise_typst(run.stdout.strip()) + "\n```\n\n")
            else:
                out.append(html)
        except (OSError, subprocess.SubprocessError):
            out.append(html)
        pos = end


def sanitise_typst(typst: str) -> str:
    """Make converted table markup safe to splice into the document.

    A table is converted separately and passed through as a raw block, so the
    sanitising done on the Markdown never reaches inside it. Three things in
    there stop typst compiling, and all three were found by rendering:

      - `image("https://journal.fibreculture.org/…")` — a figure on the
        pre-2008 domain, which typst cannot fetch and should not try to;
      - `@para88` — a cross-reference to a label that only existed in the
        original page, which typst reports as a missing label;
      - a bare `@word`, which typst reads as a citation and then complains
        that the document has no bibliography.
    """
    def image_call(m: re.Match[str]) -> str:
        # Pandoc escapes `/` inside a typst string, so the target reads
        # `https:\/\/journal…` and a pattern written for `https://` never
        # matches it.
        target = m.group(1).replace("\\", "")
        if target.startswith(("http://", "https://", "//")):
            return 'text(style: "italic")[figure not held by this archive]'
        return m.group(0)

    # The call often carries sizing arguments — `image("…", height: 2.25in,
    # width: 3in)` — so the closing bracket is not adjacent to the string.
    typst = re.sub(r'image\("([^"]*)"[^)]*\)', image_call, typst)
    # `<a href="#para6">` becomes a LINK TO A LABEL, not `@para6`; the label
    # only existed in the original page.
    typst = re.sub(r"#?link\(<para\d+>\)", "", typst)
    typst = re.sub(r"@para\d+\b", "", typst)
    typst = re.sub(r"(?<![\w@])@(?=[A-Za-z])", r"\\@", typst)
    return typst


def preprocess(body: str) -> str:
    """Make the dialect safe for pandoc, line by line.

    Paragraphs are single lines in this dialect, so the line is the unit. An
    earlier block-based version took only the marker at the end of each block
    and lost six paragraph numbers in FCJ-047, whose quoted passages hold five
    numbered paragraphs inside one blockquote.

    The number becomes a typst margin note rather than inline text: inline, a
    bare `[76]` is indistinguishable from the `[1]` footnote markers this corpus
    uses, and in print there is no colour or hover to tell them apart.
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
                line = prefix + _margin_number(marks[0]) + rest
            else:
                # The theme numbered some empty paragraphs. Nothing citable.
                line = prefix.rstrip()
        lines.append(line)
    body = "\n".join(lines)

    body = EMBED.sub(
        lambda m: f"> **Embedded media, not hosted by this archive:** <{m.group(1)}>",
        body)

    # An image the archive does not hold cannot go in a PDF: typst has no
    # network access, and should not. 19 papers reference figures on
    # `journal.fibreculture.org`, the journal's pre-2008 domain, which the
    # crawl never covered (fcj-problems.md P6). The caption survives as prose,
    # because it usually carries the figure's description and its credit, and
    # losing that is worse than losing the picture.
    def remote_image(m: re.Match[str]) -> str:
        caption = m.group(1).strip()
        return (f"*{caption}* (figure not held by this archive)"
                if caption else "*Figure not held by this archive.*")

    body = re.sub(r"!\[([^\]]*)\]\((?:https?:)?//[^)]*\)", remote_image, body)
    # And any raw `<img>` that survived inside a passed-through table, which is
    # how FCJ-039's figures reach here — as HTML attributes, not Markdown.
    body = re.sub(r"""(?is)<img[^>]*\bsrc\s*=\s*["'](?:https?:)?//[^"']*["'][^>]*>""",
                  "", body)
    return body


def _margin_number(number: str) -> str:
    """Raw typst placing a small grey number in the outer margin.

    `#place` takes it out of the text flow, so it cannot affect line breaking
    or the measure — the body text stays identical to an offprint without
    numbers, which is what "as close as possible to the later PDFs" requires.
    The left margin is 3.4cm in the template; -2.6cm puts the number in it.
    """
    return (f"`#place(left, dx: -2.6cm, dy: 0.3em, "
            f"text(size: 7pt, fill: luma(130))[{number}])`{{=typst}} ")


# --------------------------------------------------------------------------
# metadata


def pandoc_metadata(meta: dict, *, generated: str) -> list[str]:
    """`--metadata key=value` arguments for the template.

    Deliberately omits any DOI minted for the offprint itself. The `doi` here
    is the published article's, printed so a reader can reach the version of
    record — it is not an identifier for this file.
    """
    args: list[str] = []

    def add(key: str, value: object) -> None:
        if value not in (None, "", []):
            args.extend(["--metadata", f"{key}={value}"])

    add("title", meta.get("title"))
    for author in extract_list(meta.get("authors")):
        args.extend(["--metadata", f"author={author}"])
    add("affiliation", meta.get("affiliation"))
    add("fcjid", meta.get("fcj_id"))
    add("issue", meta.get("issue"))
    add("published", meta.get("published"))
    add("doi", meta.get("doi"))
    add("abstract", meta.get("abstract"))
    add("issn", meta.get("issn", "1449-1443"))
    add("licence", meta.get("licence", "Creative Commons BY-NC-ND"))
    add("sourceurl", meta.get("source_url"))
    add("generated", generated)
    return args


def extract_list(value) -> list[str]:
    if not value:
        return []
    return value if isinstance(value, list) else [value]


# --------------------------------------------------------------------------
# build


def build(content_dir: str = CONTENT, engine: str | None = None,
          only: list[str] | None = None) -> PdfReport:
    """Render an offprint for every paper that has no publisher PDF."""
    report = PdfReport()
    report.engine = engine or find_engine()
    papers_dir = os.path.join(content_dir, "papers")
    out_dir = os.path.join(content_dir, OUT_SUBDIR)
    if not os.path.isdir(papers_dir):
        return report
    os.makedirs(out_dir, exist_ok=True)
    # NO generation date. The comment here used to say "a fixed date, not
    # 'now'" while the code called `date.today()` — so every offprint carried
    # the day it happened to be built, and a no-op rebuild rewrote all 126
    # PDFs. In a repository that commits them, that is 126 modified binaries
    # for nothing, and it makes a real change impossible to see in a diff.
    #
    # The date is also the part of the provenance block that an archive least
    # needs: when a file was typeset is recorded by the repository's own
    # history, far more reliably than by a string inside the file. The
    # template omits the clause when this is empty.
    generated = ""

    for name in sorted(os.listdir(papers_dir)):
        if not name.endswith(".md"):
            continue
        slug = name[:-3]
        if only and not any(slug.startswith(p) for p in only):
            continue
        with open(os.path.join(papers_dir, name), encoding="utf-8") as fh:
            meta, body = extract.parse_front_matter(fh.read())

        if meta.get("pdf"):
            report.skipped_has_pdf.append(slug)
            continue
        if not extract_list(meta.get("authors")):
            # A PDF with no byline is worse than no PDF for deposit purposes.
            report.skipped_no_author.append(str(meta.get("fcj_id", slug)))
            continue
        if not report.engine:
            report.failed.append((slug, "no PDF engine installed"))
            continue

        source = preprocess(html_tables_to_markdown(body))
        # Figures are written root-relative (`/media/…`) because that is what
        # the website needs. Typst resolves a leading `/` against ITS project
        # root, not against `content/`, so every paper with a figure failed
        # with "file not found" — 34 of them. Rewriting to an absolute path and
        # setting typst's root to `/` makes the two agree.
        source = re.sub(r"\]\((?:\.\./)+media/",
                        f"]({os.path.join(os.path.abspath(content_dir), 'media')}/",
                        source)
        target = os.path.join(out_dir, slug + ".pdf")
        cmd = ["pandoc", "-f", "markdown+raw_html-citations", "-t", "typst",
               "--pdf-engine", report.engine, "--template", TEMPLATE,
               "-o", target]
        if report.engine == "typst":
            # `--root=/` so the absolute figure paths above resolve. This is a
            # local build of the project's own content; typst otherwise refuses
            # to read anything outside its root.
            cmd += ["--pdf-engine-opt=--root=/"]
            if os.path.isdir(FONT_DIR):
                cmd += [f"--pdf-engine-opt=--font-path={FONT_DIR}"]
        cmd += pandoc_metadata(meta, generated=generated)
        try:
            # A bounded timeout, because the failure mode here is a hang, not
            # an error: pandoc re-reading a 95,000-character grid table took
            # longer than 50 seconds and stalled a whole test run. Converting
            # one paper should take under a second.
            run = subprocess.run(cmd, input=source, capture_output=True,
                                 text=True, timeout=180)
        except (OSError, subprocess.SubprocessError) as exc:
            report.failed.append((slug, str(exc)[:200]))
            continue
        if run.returncode != 0 or not os.path.isfile(target):
            report.failed.append((slug, run.stderr.strip()[:200]))
            continue
        report.rendered.append(slug)
        report.bytes_written += os.path.getsize(target)

    return report


def _main() -> None:
    import sys
    only = sys.argv[1:] or None
    report = build(only=only)
    print(f"engine: {report.engine or 'NONE INSTALLED'}")
    print(f"  rendered            : {len(report.rendered)}"
          f" ({report.bytes_written / 1024 / 1024:.1f} MB)")
    print(f"  skipped, has a PDF  : {len(report.skipped_has_pdf)}")
    print(f"  skipped, no author  : {len(report.skipped_no_author)}"
          f" {' '.join(report.skipped_no_author)}")
    print(f"  failed              : {len(report.failed)}")
    for slug, why in report.failed[:6]:
        print(f"      {slug[:40]}: {why[:120]}")
    if not report.engine:
        print()
        print("  No PDF engine is installed, so nothing was rendered.")
        print("  `brew install typst` is the intended one: a single binary,")
        print("  supported natively by pandoc, no TeX tree.")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    _main()
