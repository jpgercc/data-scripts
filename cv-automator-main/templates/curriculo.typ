// =============================================================
// Perfect CV — Typst Template
// ATS-friendly: 100% selectable text, linear reading order,
// embedded fonts, no rasterization.
// =============================================================

// ── Dados injetados pelo compiler.py ─────────────────────────
#let dados = json("dados_curriculo.json")

// ── Configuração da página ────────────────────────────────────
#set page(
  paper: "a4",
  margin: (top: 1.8cm, bottom: 1.8cm, left: 2cm, right: 2cm),
)

// ── Tipografia ────────────────────────────────────────────────
#set text(font: "Liberation Sans", size: 10pt, lang: "pt")
#set par(leading: 0.6em, justify: true)

// ── Utilitários ──────────────────────────────────────────────
#let section-title(title) = {
  v(0.6em)
  text(weight: "bold", size: 11pt, upper(title))
  line(length: 100%, stroke: 0.5pt + black)
  v(0.2em)
}

#let bullet-item(content) = {
  grid(
    columns: (0.8em, 1fr),
    gutter: 0pt,
    [•], content,
  )
}

// =============================================================
// CABEÇALHO
// =============================================================
#align(center)[
  #text(size: 18pt, weight: "bold")[#dados.nome]
  #v(0.15em)
  #text(size: 11pt, weight: "regular")[#dados.titulo]
  #v(0.3em)
  #text(size: 9pt)[
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

#v(0.5em)

// =============================================================
// RESUMO PROFISSIONAL
// =============================================================
#if dados.keys().contains("resumo") and dados.resumo != "" {
  section-title("Resumo Profissional")
  text[#dados.resumo]
  v(0.3em)
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
        #text(size: 9pt)[#exp.periodo]
      ],
    )
    v(0.15em)
    for resp in exp.responsabilidades {
      bullet-item(text[#resp])
      v(0.1em)
    }
    v(0.3em)
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
      columns: (3.5cm, 1fr),
      gutter: 0pt,
      text(weight: "bold")[#upper(categoria) #h(0.3em)],
      text[#itens-str],
    )
    v(0.2em)
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
        #text(size: 9pt)[#f.periodo]
      ],
    )
    v(0.2em)
  }
}

// =============================================================
// CERTIFICAÇÕES
// =============================================================
#if dados.keys().contains("certificacoes") and dados.certificacoes.len() > 0 {
  section-title("Certificações")

  for cert in dados.certificacoes {
    bullet-item(text[#cert])
    v(0.1em)
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
