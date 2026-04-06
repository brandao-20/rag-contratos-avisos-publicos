import React from 'react'

export default function CorpusExplorer({ sections, onAsk }) {
  const totalUniqueSources = sections.find((section) => section.id === 'todos')?.sources_count
    || new Set(
      sections.flatMap((section) => (section.sources || []).map((source) => source.source_id)).filter(Boolean),
    ).size

  return (
    <section className="panel explorer-panel">
      <div className="panel-header panel-header-tight">
        <div>
          <div className="eyebrow">Explorar corpus</div>
          <h3>Documentos e pontos de entrada</h3>
        </div>
        <span>{totalUniqueSources} fontes únicas</span>
      </div>
      <div className="explorer-grid">
        {sections.map((section) => (
          <article key={section.id} className="explorer-card">
            <div className="explorer-card-head">
              <div>
                <h4>{section.label}</h4>
                <p>{section.description}</p>
              </div>
              <span className="inline-badge">{section.sources_count}</span>
            </div>
            {section.example_questions?.length ? (
              <div className="explorer-block">
                <div className="message-section-label">Perguntas de exemplo</div>
                <div className="chip-row">
                  {section.example_questions.map((question) => (
                    <button key={question} type="button" className="chip" onClick={() => onAsk(question)}>
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
            {section.sources?.length ? (
              <div className="explorer-block">
                <div className="message-section-label">Fontes</div>
                <div className="explorer-source-list">
                  {section.sources.map((source) => (
                    <div className="explorer-source" key={`${section.id}-${source.source_id}`}>
                      <div>
                        <strong>{source.title}</strong>
                        <div className="explorer-source-meta">{[source.entity, source.document_type].filter(Boolean).join(' • ')}</div>
                      </div>
                      {source.source_url ? (
                        <a href={source.source_url} target="_blank" rel="noreferrer" className="text-link">
                          Abrir
                        </a>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="empty-panel empty-panel-compact">Sem fontes desta categoria no manifesto atual.</div>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}
