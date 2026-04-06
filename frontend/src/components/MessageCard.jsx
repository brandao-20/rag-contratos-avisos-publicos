import React from 'react'
import { classNames, formatCitationCountLabel, formatDateTime } from '../utils/format'

function MarkdownBlock({ text }) {
  if (!text) return null
  const lines = text.split('\n')
  const nodes = []
  let listItems = []
  let numbered = false
  let key = 0

  function flushList() {
    if (!listItems.length) return
    const Tag = numbered ? 'ol' : 'ul'
    nodes.push(<Tag key={`list-${key++}`} className="markdown-list">{listItems}</Tag>)
    listItems = []
    numbered = false
  }

  for (const line of lines) {
    const h2 = line.match(/^##\s+(.+)/)
    if (h2) {
      flushList()
      nodes.push(<h4 key={key++} className="markdown-h3">{renderInline(h2[1])}</h4>)
      continue
    }

    const numberedItem = line.match(/^\d+\.\s+(.+)/)
    if (numberedItem) {
      numbered = true
      listItems.push(<li key={key++}>{renderInline(numberedItem[1])}</li>)
      continue
    }

    const bullet = line.match(/^[-*•]\s+(.+)/)
    if (bullet) {
      listItems.push(<li key={key++}>{renderInline(bullet[1])}</li>)
      continue
    }

    flushList()
    if (!line.trim()) {
      nodes.push(<div key={key++} className="markdown-spacer" />)
    } else {
      nodes.push(<p key={key++} className="markdown-p">{renderInline(line)}</p>)
    }
  }

  flushList()
  return <div className="markdown-content">{nodes}</div>
}

function renderInline(text) {
  const parts = String(text || '').split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[\d+\])/g)
  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={index}>{part.slice(2, -2)}</strong>
    if (part.startsWith('*') && part.endsWith('*')) return <em key={index}>{part.slice(1, -1)}</em>
    if (part.startsWith('`') && part.endsWith('`')) return <code key={index} className="markdown-code">{part.slice(1, -1)}</code>
    if (/^\[\d+\]$/.test(part)) return <sup key={index} className="citation-ref">{part}</sup>
    return part
  })
}

function FollowUpChips({ questions, onUse }) {
  if (!questions?.length) return null
  return (
    <div className="followups-block">
      <div className="message-section-label">Sugestões de seguimento</div>
      <div className="chip-row">
        {questions.map((question) => (
          <button key={question} type="button" className="chip chip-followup" onClick={() => onUse(question)}>
            {question}
          </button>
        ))}
      </div>
    </div>
  )
}

function ProceduralSteps({ steps }) {
  if (!steps?.length) return null
  return (
    <div className="steps-card">
      <div className="message-section-label">Passos do procedimento</div>
      <ol className="steps-list">
        {steps.map((step) => <li key={step}>{step}</li>)}
      </ol>
    </div>
  )
}

export default function MessageCard({
  message,
  payload,
  selected,
  onSelect,
  onCopy,
  copied,
  onFavorite,
  favorite,
  onUseFollowUp,
  showFollowUps = false,
}) {
  const isAssistant = message?.role === 'assistant'
  return (
    <article className={classNames('message-card', isAssistant ? 'message-assistant' : 'message-user', selected && 'message-selected')}>
      <div className="message-shell">
        <div className={classNames('message-avatar', isAssistant ? 'message-avatar-assistant' : 'message-avatar-user')}>
          {isAssistant ? 'IA' : 'Tu'}
        </div>
        <div className="message-body">
          <div className="message-header-row">
            <div>
              <div className="message-role">{isAssistant ? 'Assistente' : 'Pergunta'}</div>
              {payload?.createdAt ? <div className="message-meta-row">{formatDateTime(payload.createdAt)}</div> : null}
            </div>
            {isAssistant && payload ? (
              <div className="message-badges">
                {payload.confidence?.label ? <span className={`confidence-badge confidence-${payload.confidence.label}`}>{payload.confidence.label}</span> : null}
                {payload.answer?.citations_count ? <span className="inline-badge">{formatCitationCountLabel(payload.answer.citations_count)}</span> : null}
                {payload.answer?.elapsed_ms ? <span className="inline-badge">{payload.answer.elapsed_ms} ms</span> : null}
              </div>
            ) : null}
          </div>

          <button type="button" className={classNames('message-content-button', isAssistant && 'message-content-button-assistant')} onClick={isAssistant && payload ? onSelect : undefined}>
            <MarkdownBlock text={message?.content || ''} />
          </button>

          {isAssistant && payload ? (
            <>
              <ProceduralSteps steps={payload.proceduralSteps} />
              {showFollowUps ? <FollowUpChips questions={payload.followUps} onUse={onUseFollowUp} /> : null}
              <div className="message-actions-row">
                <button type="button" className="text-button" onClick={onCopy}>{copied ? 'Copiado' : 'Copiar'}</button>
                <button
                  type="button"
                  className={classNames('favorite-star-button', favorite && 'favorite-star-button-active')}
                  onClick={(event) => {
                    event.preventDefault()
                    event.stopPropagation()
                    onFavorite?.()
                  }}
                  title={favorite ? 'Remover dos favoritos' : 'Adicionar aos favoritos'}
                  aria-label={favorite ? 'Remover dos favoritos' : 'Adicionar aos favoritos'}
                >
                  <svg viewBox="0 0 24 24" className="favorite-star-icon" aria-hidden="true">
                    <path d="M12 3.6l2.6 5.26 5.81.84-4.2 4.09.99 5.79L12 16.85 6.8 19.58l.99-5.79-4.2-4.09 5.81-.84L12 3.6z" />
                  </svg>
                </button>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </article>
  )
}
