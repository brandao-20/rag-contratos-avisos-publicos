import React from 'react'

export default function HeroHome({ suggestions, onAsk, disabled }) {
  return (
    <section className="hero-home panel">
      <h1>Consulta documental de contratos e avisos públicos</h1>
      <p>
        Explora perguntas sobre objeto, entidade adjudicante, prazos, preço base, critérios,
        caução, CPV, lotes, local de execução e requisitos. Esta demonstração usa um corpus curado
        de anúncios de procedimento para reduzir saltos semânticos e manter as respostas ancoradas em procedimentos concretos.
      </p>
      <div className="hero-home-suggestions">
        {suggestions.map((question) => (
          <button
            key={question}
            type="button"
            className="chip hero-chip"
            onClick={() => onAsk(question)}
            disabled={disabled}
          >
            {question}
          </button>
        ))}
      </div>
    </section>
  )
}
