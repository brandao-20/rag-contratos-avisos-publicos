import React from 'react'

export default function GlossaryView({ entries, search, onSearch, category, onCategory }) {
  const categories = ['todos', ...Array.from(new Set(entries.map((entry) => entry.category || 'outros')))]
  const filtered = entries.filter((entry) => {
    const matchesCategory = category === 'todos' || entry.category === category
    const haystack = `${entry.term} ${entry.short_definition} ${entry.why_it_matters} ${(entry.related_terms || []).join(' ')}`.toLowerCase()
    const matchesSearch = !search.trim() || haystack.includes(search.trim().toLowerCase())
    return matchesCategory && matchesSearch
  })

  return (
    <section className="panel glossary-panel">
      <div className="panel-header panel-header-tight">
        <div>
          <div className="eyebrow">Glossário</div>
          <h3>Termos do domínio</h3>
        </div>
        <span>{filtered.length} termos</span>
      </div>

      <div className="glossary-filters">
        <input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Pesquisar termo…" />
        <select value={category} onChange={(event) => onCategory(event.target.value)}>
          {categories.map((item) => (
            <option key={item} value={item}>{item === 'todos' ? 'Todas as categorias' : item}</option>
          ))}
        </select>
      </div>

      <div className="glossary-grid">
        {filtered.map((entry) => (
          <article key={entry.term} className="glossary-card">
            <div className="glossary-card-head">
              <h4>{entry.term}</h4>
              <span className="inline-badge">{entry.category}</span>
            </div>
            <p>{entry.short_definition}</p>
            <div className="message-section-label">Porque importa</div>
            <p>{entry.why_it_matters}</p>
            {entry.related_terms?.length ? (
              <div className="related-tags">
                {entry.related_terms.map((term) => <span key={`${entry.term}-${term}`} className="chip chip-static">{term}</span>)}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  )
}
