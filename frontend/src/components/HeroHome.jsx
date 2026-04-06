import React from 'react'

export default function HeroHome({ suggestions, onAsk, disabled }) {
  return (
    <section className="hero-home panel">
      <div className="hero-home-icon" aria-hidden="true">◇</div>
      <h1>Leitura assistida de contratação pública</h1>
      <p>
        Coloca perguntas em linguagem natural sobre objeto, entidade adjudicante, prazos,
        preço base, critérios, caução, CPV, lotes, local de execução e requisitos. A resposta
        privilegia extração direta, síntese curta quando o LLM está disponível e citações claras
        para validação documental.
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
