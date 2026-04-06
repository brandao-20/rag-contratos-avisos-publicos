import React from 'react'

export default function HeroHome({ suggestions, onAsk, disabled }) {
  return (
    <section className="hero-home panel">
      <h1>Consulta documental de contratação pública</h1>
      <p>
        Explora perguntas sobre objeto, entidade adjudicante, prazos, preço base, critérios,
        caução, CPV, lotes, local de execução e requisitos. O sistema privilegia extração direta,
        citações claras e fallback documental quando o motor local não está disponível.
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
