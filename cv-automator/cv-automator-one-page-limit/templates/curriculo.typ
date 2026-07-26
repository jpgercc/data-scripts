// =============================================================
// Perfect CV — Typst Template
// ATS-friendly: 100% selectable text, linear reading order,
// embedded fonts, no rasterization.
// =============================================================

// ── Dados injetados pelo compiler.py ─────────────────────────
#let dados = json("dados_curriculo.json")

// Preset de densidade escolhido pelo compiler.py.
#let layout = if dados.keys().contains("layout") { dados.layout } else { (: ) }
#let preset = if layout.keys().contains("preset") { layout.preset } else { "balanced" }

#let page-margin = if preset == "compact-3" {
  (top: 0.9cm, bottom: 0.9cm, left: 1.15cm, right: 1.15cm)
} else if preset == "compact-2" {
  (top: 1.05cm, bottom: 1.05cm, left: 1.25cm, right: 1.25cm)
} else if preset == "compact-1" {
  (top: 1.35cm, bottom: 1.35cm, left: 1.55cm, right: 1.55cm)
} else {
  (top: 1.8cm, bottom: 1.8cm, left: 2cm, right: 2cm)
}

#let body-size = if preset == "compact-3" {
  8.7pt
} else if preset == "compact-2" {
  9pt
} else if preset == "compact-1" {
  9.5pt
} else {
  10pt
}

#let body-leading = if preset == "compact-3" {
  0.45em
} else if preset == "compact-2" {
  0.5em
} else if preset == "compact-1" {
  0.55em
} else {
  0.6em
}

#let header-name-size = if preset == "compact-3" {
  16pt
} else if preset == "compact-2" {
  16.5pt
} else if preset == "compact-1" {
  17pt
} else {
  18pt
}

#let header-title-size = if preset == "compact-3" {
  10pt
} else if preset == "compact-2" {
  10.5pt
} else if preset == "compact-1" {
  11pt
} else {
  11pt
}

#let section-title-size = if preset == "compact-3" {
  10pt
} else if preset == "compact-2" {
  10.5pt
} else if preset == "compact-1" {
  11pt
} else {
  11pt
}

#let section-gap = if preset == "compact-3" {
  0.2em
} else if preset == "compact-2" {
  0.22em
} else if preset == "compact-1" {
  0.25em
} else {
  0.3em
}

#let section-top-gap = if preset == "compact-3" {
  0.4em
} else if preset == "compact-2" {
  0.45em
} else if preset == "compact-1" {
  0.55em
} else {
  0.6em
}

#let section-rule-gap = if preset == "compact-3" {
  0.12em
} else if preset == "compact-2" {
  0.15em
} else if preset == "compact-1" {
  0.18em
} else {
  0.2em
}

#let item-gap = if preset == "compact-3" {
  0.05em
} else if preset == "compact-2" {
  0.07em
} else if preset == "compact-1" {
  0.1em
} else {
  0.15em
}

#let bullet-gap = if preset == "compact-3" {
  0.03em
} else if preset == "compact-2" {
  0.05em
} else if preset == "compact-1" {
  0.07em
} else {
  0.1em
}

#let bullet-width = if preset == "compact-3" {
  0.6em
} else if preset == "compact-2" {
  0.65em
} else if preset == "compact-1" {
  0.7em
} else {
  0.8em
}

#let skills-label-width = if preset == "compact-3" {
  3.0cm
} else if preset == "compact-2" {
  3.15cm
} else if preset == "compact-1" {
  3.3cm
} else {
  3.5cm
}

#let meta-size = if preset == "compact-3" {
  8pt
} else if preset == "compact-2" {
  8.5pt
} else {
  9pt
}

// ── Configuração da página ────────────────────────────────────
#set page(
  paper: "a4",
  margin: page-margin,
)

// ── Tipografia ────────────────────────────────────────────────
#set text(font: "Liberation Sans", size: body-size, lang: "pt")
#set par(leading: body-leading, justify: true)

// ── Utilitários ──────────────────────────────────────────────
#let section-title(title) = {
  v(section-top-gap)
  text(weight: "bold", size: section-title-size, upper(title))
  line(length: 100%, stroke: 0.5pt + black)
  v(section-rule-gap)
}

#let bullet-item(content) = {
  grid(
    columns: (bullet-width, 1fr),
    gutter: 0pt,
    [•], content,
  )
}

// =============================================================
// CABEÇALHO
// =============================================================
#align(center)[
  #text(size: header-name-size, weight: "bold")[#dados.nome]
  #v(0.12em)
  #text(size: header-title-size, weight: "regular")[#dados.titulo]
  #v(0.22em)
  #text(size: meta-size)[
    #dados.email
    #h(1em) | #h(1em)
    #dados.telefone
    #if dados.keys().contains("linkedin") and dados.linkedin != "" [
      #h(1em) | #h(1em)
      #dados.linkedin
    ]
    #if dados.keys().contains("github") and dados.github != "" [
      #h(1em) | #h(1em)
      #dados.github
    ]
    #if dados.keys().contains("localizacao") and dados.localizacao != "" [
      #h(1em) | #h(1em)
      #dados.localizacao
    ]
  ]
]

#v(section-gap)

// =============================================================
// RESUMO PROFISSIONAL
// =============================================================
#if dados.keys().contains("resumo") and dados.resumo != "" {
  section-title("Resumo Profissional")
  text[#dados.resumo]
  v(section-gap)
}

// =============================================================
// EXPERIÊNCIA PROFISSIONAL
// =============================================================
#if dados.keys().contains("experiencias") and dados.experiencias.len() > 0 {
  section-title("Experiência Profissional")

  for exp in dados.experiencias {
    grid(
      columns: (1fr, auto),
      gutter: 0pt,
      [
        #text(weight: "bold")[#exp.cargo] — #text(style: "italic")[#exp.empresa]
      ],
      [
        #text(size: meta-size)[#exp.periodo]
      ],
    )
    v(item-gap)
    for resp in exp.responsabilidades {
      bullet-item(text[#resp])
      v(bullet-gap)
    }
    v(section-gap)
  }
}

// =============================================================
// HABILIDADES TÉCNICAS
// =============================================================
#if dados.keys().contains("habilidades") and dados.habilidades.len() > 0 {
  section-title("Habilidades Técnicas")

  for (categoria, itens) in dados.habilidades {
    let itens-str = if type(itens) == array { itens.join(", ") } else { itens }
    grid(
      columns: (skills-label-width, 1fr),
      gutter: 0pt,
      text(weight: "bold")[#upper(categoria) #h(0.3em)],
      text[#itens-str],
    )
    v(item-gap)
  }
}

// =============================================================
// FORMAÇÃO ACADÊMICA
// =============================================================
#if dados.keys().contains("formacao") and dados.formacao.len() > 0 {
  section-title("Formação Acadêmica")

  for f in dados.formacao {
    grid(
      columns: (1fr, auto),
      gutter: 0pt,
      [
        #text(weight: "bold")[#f.curso] — #text(style: "italic")[#f.instituicao]
      ],
      [
        #text(size: meta-size)[#f.periodo]
      ],
    )
    v(item-gap)
  }
}

// =============================================================
// CERTIFICAÇÕES
// =============================================================
#if dados.keys().contains("certificacoes") and dados.certificacoes.len() > 0 {
  section-title("Certificações")

  for cert in dados.certificacoes {
    bullet-item(text[#cert])
    v(bullet-gap)
  }
}

// =============================================================
// IDIOMAS
// =============================================================
#if dados.keys().contains("idiomas") and dados.idiomas.len() > 0 {
  section-title("Idiomas")

  let idiomas-str = dados.idiomas.map(i => i.idioma + ": " + i.nivel).join("   |   ")
  text[#idiomas-str]
}
