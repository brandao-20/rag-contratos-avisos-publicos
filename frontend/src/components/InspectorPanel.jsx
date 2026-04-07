import React from 'react'
import { STRUCTURED_LABELS } from '../constants'
import { classNames, renderStructuredValue } from '../utils/format'
import SourceCard from './SourceCard'

function ConfidenceBadge({ confidence }) {
  const label = confidence?.label || 'desconhecida'
  return (
    <span className={classNames('confidence-badge', `confidence-${label}`)}>
      {label}
      {typeof confidence?.score === 'number' ? ` · ${Math.round(confidence.score * 100)}%` : ''}
    </span>
  )
}

/** Alerta de incoerência: campos mostrados mas confiança baixa */
function FieldsLowConfidenceWarning({ confidence, hasFields }) {
  if (!hasFields) return null
  if (!confidence || confidence.label !== 'baixa') return null
  return (
    <div className="fields-confidence-warning" role="alert">
      <span className="warning-icon" aria-hidden="true">⚠</span>
      <span>
        A resposta principal tem <strong>confiança baixa</strong>. Os campos abaixo são
        extraídos diretamente do documento e podem estar parcialmente corretos, mas
        devem ser verificados na fonte antes de serem usados.
      </span>
    </div>
  )
}

function StructuredGrid({ structuredData, confidence }) {
  const entries = Object.entries(structuredData || {}).filter(([key, value]) => {
    // Filtra metadados internos (campo de proveniência)
    if (key.startsWith('_')) return false
    if (value == null) return false
    if (Array.isArray(value)) return value.length > 0
    if (typeof value === 'string') return value.trim().length > 0
    return true
  })

  if (!entries.length) {
    return <div className="empty-panel">Sem extração estruturada disponível para esta resposta.</div>
  }

  // Mapa de proveniência por campo (opcional — enviado pelo backend como _field_citations)
  const fieldCitations = structuredData?._field_citations || {}

  return (
    <>
      <FieldsLowConfidenceWarning confidence={confidence} hasFields={entries.length > 0} />
      <div className="structured-grid">
        {entries.map(([key, value]) => {
          const rendered = renderStructuredValue(key, value)
          const citationIdx = fieldCitations[key]
          return (
            <div className="structured-card" key={key}>
              <div className="structured-label">
                {STRUCTURED_LABELS[key] || key.replace(/_/g, ' ')}
                {citationIdx != null ? (
                  <sup className="field-source-badge" title={`Extraído da citação [${citationIdx}]`}>
                    [{citationIdx}]
                  </sup>
                ) : null}
              </div>
              {Array.isArray(rendered) ? (
                <ul className="structured-ref-list">
                  {rendered.map((item) => (
                    <li key={item.id}>
                      <sup className="citation-ref">{item.citation}</sup> {item.summary}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="structured-value">{rendered}</div>
              )}
            </div>
          )
        })}
      </div>
    </>
  )
}

function MetadataPanel({ payload, debugMode }) {
  const answer = payload?.answer || {}
  const confidence = payload?.confidence || {}
  const retrievalBackend = answer.retrieval_backend === 'vector' ? 'Vetorial' : answer.retrieval_backend === 'lexical' ? 'Lexical' : '—'
  return (
    <div className="meta-stack">
      <div className="meta-grid">
        <div className="meta-item"><div className="meta-label">Intenção</div><div className="meta-value">{answer.intent || '—'}</div></div>
        <div className="meta-item"><div className="meta-label">Citações</div><div className="meta-value">{answer.citations_count ?? '—'}</div></div>
        <div className="meta-item"><div className="meta-label">Tempo</div><div className="meta-value">{answer.elapsed_ms ? `${answer.elapsed_ms} ms` : '—'}</div></div>
        <div className="meta-item"><div className="meta-label">Modo de resposta</div><div className="meta-value">{answer.response_mode === 'llm' ? (answer.llm_label || 'LLM') : 'Extração direta'}</div></div>
        <div className="meta-item"><div className="meta-label">Retrieval</div><div className="meta-value">{retrievalBackend}</div></div>
        <div className="meta-item meta-item-wide"><div className="meta-label">Fonte principal</div><div className="meta-value">{answer.primary_source_title || answer.primary_source_id || '—'}</div></div>
      </div>
      <div className="meta-card">
        <div className="meta-label">Confiança</div>
        <ul className="reason-list">
          {(confidence.reasons || []).map((reason) => <li key={reason}>{reason}</li>)}
        </ul>
      </div>
      {debugMode ? (
        <div className="meta-card">
          <div className="meta-label">Query de retrieval</div>
          <div className="meta-query">{answer.retrieval_query || '—'}</div>
        </div>
      ) : null}
    </div>
  )
}

function CitationInspector({ citation }) {
  if (!citation) return <div className="empty-panel">Seleciona uma citação individual para inspecionar o excerto.</div>
  return (
    <div className="citation-inspector-card">
      <div className="citation-locator-strong">{citation.locator || 'Trecho'} · {citation.source?.title || citation.source?.source_id}</div>
      <div className="citation-inspector-excerpt">{citation.excerpt || 'Sem excerto disponível.'}</div>
      <div className="citation-actions-row">
        {citation.source?.source_url ? (
          <a className="text-link" href={citation.source.source_url} target="_blank" rel="noreferrer">Abrir fonte</a>
        ) : null}
      </div>
    </div>
  )
}

export default function InspectorPanel({
  selectedPayload,
  selectedTab,
  onChangeTab,
  selectedCitation,
  onSelectCitation,
  debugMode,
}) {
  const tabs = [
    { id: 'fontes', label: 'Fontes' },
    { id: 'campos', label: 'Campos' },
    { id: 'citacao', label: 'Citação' },
    { id: 'metadados', label: 'Metadados' },
  ]

  return (
    <aside className="inspector-column">
      <section className="panel inspector-panel sticky-panel">
        <div className="panel-header panel-header-tight">
          <h3>Inspeção</h3>
          {selectedPayload ? <ConfidenceBadge confidence={selectedPayload.confidence} /> : null}
        </div>

        {!selectedPayload ? (
          <div className="empty-panel">Seleciona uma resposta para inspecionar fontes, campos, citações e metadados.</div>
        ) : (
          <>
            <div className="tab-row" role="tablist" aria-label="Inspeção da resposta">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  className={classNames('tab-button', selectedTab === tab.id && 'tab-button-active')}
                  onClick={() => onChangeTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {selectedTab === 'fontes' ? (
              <div className="source-list">
                {(selectedPayload.sources || []).length ? (
                  selectedPayload.sources.map((source) => (
                    <SourceCard
                      key={`${source.source_id}-${source.title}`}
                      source={source}
                      onSelectCitation={(citation) => {
                        onSelectCitation(citation)
                        onChangeTab('citacao')
                      }}
                      activeCitationKey={selectedCitation ? `${selectedCitation.source?.source_id}:${selectedCitation.index}` : null}
                    />
                  ))
                ) : (
                  <div className="empty-panel">Sem fontes agrupadas nesta resposta.</div>
                )}
              </div>
            ) : null}

            {selectedTab === 'campos' ? (
              <StructuredGrid
                structuredData={selectedPayload.structuredData}
                confidence={selectedPayload.confidence}
              />
            ) : null}
            {selectedTab === 'citacao' ? <CitationInspector citation={selectedCitation} /> : null}
            {selectedTab === 'metadados' ? <MetadataPanel payload={selectedPayload} debugMode={debugMode} /> : null}
          </>
        )}
      </section>
    </aside>
  )
}
