// Fibreculture Journal archive - created by Mathew Wall-Smith. Apache-2.0; see NOTICE.
// Pandoc/typst template for a Fibreculture Journal archival offprint.
//
// Reproduces the layout of the journal's own later PDFs (issues 17-30), which
// were produced with Asciidoctor PDF in 2017. Measured from
// FCJ-218PaulaBialski.pdf rather than guessed: A4, single column, full text
// width, ragged right, Open Sans, `FCJ-nnn ` before the title, a one-line
// byline, `Abstract:` bold inline, a `doi:` line, unnumbered bold headings,
// references as a bulleted hanging-indent list, page number in the footer and
// no running header.
//
// Two things here are NOT in those PDFs, and both are deliberate:
//
//   1. The paragraph number in the outer margin. For issues 1-16 the numbered
//      HTML was the only published form, so citations to those papers cite
//      paragraphs. An offprint that drops the numbers cannot support those
//      citations. Small, grey, in the margin: present for citation, out of the
//      way of reading.
//   2. The provenance block in the footer of page 1. A generated offprint is
//      NOT the version of record for these issues — the HTML is — and it must
//      say so, or the archive has manufactured a second citable object for the
//      same paper.

// Helpers pandoc's typst WRITER emits and its default template defines. A
// custom template replaces that default, so they have to be declared here or
// every paper containing a `---` fails with "unknown variable: horizontalrule".
#let horizontalrule = line(start: (25%, 0%), end: (75%, 0%))

#show terms: it => {
  it.children
    .map(child => [#strong[#child.term]#h(0.5em)#child.description])
    .join()
}

#let conf(
  title: none,
  authors: (),
  affiliation: none,
  fcjid: none,
  issue: none,
  published: none,
  // `doi` and `sourceurl` are CONTENT, not strings, and are printed rather
  // than linked. Pandoc escapes `/` as `\/` inside a typst string literal,
  // which typst rejects — and every DOI and URL here contains slashes. Plain
  // text in a colophon is also what the journal's own PDFs show.
  doi: none,
  abstract: none,
  journal: "The Fibreculture Journal",
  issn: none,
  licence: none,
  sourceurl: none,
  generated: none,
  // Plain STRINGS, separate from the content values above. `set document`
  // takes strings, and pandoc hands the template content for `title` and
  // `author` — "expected string, found content". These carry the same values
  // in the form the PDF's own metadata needs, which is what a repository
  // reads when the file is deposited.
  pdftitle: none,
  pdfauthors: (),
  doc,
) = {
  if pdftitle != none {
    set document(title: pdftitle, author: pdfauthors)
  }

  set page(
    paper: "a4",
    margin: (left: 3.4cm, right: 2.2cm, top: 2.4cm, bottom: 2.2cm),
    numbering: "1",
    number-align: center,
  )

  // 9.5pt matches the measured body size of the later PDFs; `justify: false`
  // matches their ragged right edge.
  set text(font: "Open Sans", size: 9.5pt, lang: "en", hyphenate: false)
  set par(justify: false, leading: 0.62em, spacing: 0.9em, first-line-indent: 0pt)

  // Unnumbered, bold, with more space above than below so a heading binds to
  // the text it introduces.
  show heading: it => block(above: 1.5em, below: 0.65em)[
    #set text(weight: "bold", size: if it.level <= 1 { 11pt } else { 10pt })
    #it.body
  ]

  show quote.where(block: true): it => block(
    inset: (left: 1.2em, right: 0.6em), above: 1em, below: 1em,
  )[#set text(size: 9pt); #it.body]

  show figure.caption: it => block(width: 100%)[
    #set text(size: 8.5pt, fill: rgb("#555555"))
    #it.body
  ]
  show figure: it => block(above: 1.4em, below: 1.4em, width: 100%, it)

  // References: a bulleted hanging-indent list, as in the later PDFs.
  set list(marker: [•], indent: 0.4em, body-indent: 0.6em, spacing: 0.7em)

  // ---- title block
  block(below: 0.4em)[
    #set text(size: 15pt, weight: "bold")
    #if fcjid != none [#fcjid ]#title
  ]
  // Built in CODE mode, not markup. Chaining `#if … []#if … []` inside a
  // content block is a syntax error in typst 0.15, and the message points at
  // the `#if` rather than at the chain, which is not obvious.
  if authors.len() > 0 {
    block(below: 1.4em, {
      set text(size: 10pt)
      authors.join(", ", last: " and ")
      if affiliation != none [, #affiliation]
      [.]
    })
  }
  if abstract != none and abstract != "" {
    block(below: 1.1em, width: 100%)[
      #set text(size: 9pt)
      #strong[Abstract:] #abstract
    ]
  }
  if doi != none {
    block(below: 1.6em)[
      #set text(size: 9pt)
      doi: #doi
    ]
  }

  doc

  // ---- provenance, at the end so it is read as a colophon rather than a
  // header, and so it travels with the file wherever it is deposited.
  v(1.6em)
  line(length: 100%, stroke: 0.4pt + rgb("#aaaaaa"))
  block(above: 0.8em, {
    set text(size: 7.5pt, fill: rgb("#555555"))
    journal
    if issn != none [ (ISSN #issn)]
    if issue != none [ — Issue #issue]
    if published != none [, #published]
    [. ]
    if licence != none [This article is published under #licence. ]
    [The author retains copyright.]
    linebreak()
    [*This PDF is an archival offprint generated from the journal's text archive*]
    if generated != none [ on #generated]
    [. It is not the publisher's version of record]
    if sourceurl != none [; the published article is at #sourceurl]
    [. Page numbers here are not the published pagination. Where paragraph ]
    [numbers appear in the margin they are the journal's own and are the ]
    [citable unit.]
  })
}

#show: doc => conf(
$if(title)$
  title: [$title$],
$endif$
$if(fcjid)$
  fcjid: [$fcjid$],
$endif$
  authors: (
$for(author)$
    [$author$],
$endfor$
  ),
$if(affiliation)$
  affiliation: [$affiliation$],
$endif$
$if(issue)$
  issue: [$issue$],
$endif$
$if(published)$
  published: [$published$],
$endif$
$if(doi)$
  doi: [$doi$],
$endif$
$if(abstract)$
  abstract: [$abstract$],
$endif$
$if(issn)$
  issn: [$issn$],
$endif$
$if(licence)$
  licence: [$licence$],
$endif$
$if(sourceurl)$
  sourceurl: [$sourceurl$],
$endif$
$if(generated)$
  generated: [$generated$],
$endif$
$if(title)$
  pdftitle: "$fcjid$ $title$",
$endif$
  pdfauthors: ($for(author)$"$author$", $endfor$),
  doc,
)

$body$
