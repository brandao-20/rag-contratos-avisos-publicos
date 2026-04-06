import React from 'react'
import { formatCitationCountLabel, sameNormalizedLabel } from '../utils/format'

export default function SourceCard({ source, onSelectCitation, activeCitationKey }) {
  const meta = [source.document_type, source.entity, source.pages_label || source.primary_locator].filter(Boolean)
  const citations = source.citations || []
  const sourceTitle = source.title || source.source_id || 'Fonte'
  const showSourceIdBadge = source.source_id && !sameNormalizedLabel(source.source_id, sourceTitle)

  return (
    <article className="source-card">
      <div className="source-card-top">
        <div className="source-card-main">
          <div className="source-card-title-row">
            <h4>{sourceTitle}</h4>
            {showSourceIdBadge ? <span className="inline-badge">{source.source_id}</span> : null}
          </div>
          <p className="source-card-meta">{meta.join(' • ') || 'Sem metadados adicionais'}</p>
        </div>
        <div className="source-card-actions">
          {citations.length ? <span className="inline-badge">{formatCitationCountLabel(citations.length)}</span> : null}
          {source.source_url ? (
            <a href={source.source_url} target="_blank" rel="noreferrer" className="text-link">
              Abrir fonte
            </a>
          ) : null}
        </div>
      </div>

      {source.primary_excerpt ? <p className="source-excerpt">{source.primary_excerpt}</p> : null}

      {citations.length ? (
        <div className="citation-list">
          {citations.slice(0, 3).map((citation) => {
            const citationKey = `${source.source_id}:${citation.index}`
            return (
              <button
                key={citationKey}
                type="button"
                className={`citation-item ${activeCitationKey === citationKey ? 'citation-item-active' : ''}`}
                onClick={() => onSelectCitation({ ...citation, source })}
              >
                <div className="citation-locator">{citation.locator || 'Trecho'}</div>
                <div className="citation-excerpt">{citation.excerpt}</div>
              </button>
            )
          })}
        </div>
      ) : null}
    </article>
  )
}
