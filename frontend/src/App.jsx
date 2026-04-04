import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'

const DEFAULT_API_BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL).replace(/\/$/, '')

const FALLBACK_CATEGORIES = [
  { id: 'todos', label: 'Todos os documentos' },
  { id: 'contratacao_publica', label: 'Contratação pública' },
  { id: 'aviso_publico', label: 'Avisos públicos' },
  { id: 'documento_publico', label: 'Outros documentos públicos' },
]
const FALLBACK_SUGGESTIONS = [
  'Qual é o objeto deste aviso ou contrato?',
  'Existe preço base ou valor base?',
  'Qual é o prazo para apresentação das propostas?',
  'Existe prestação de caução?',
  'Qual é o CPV indicado?',
  'Que critérios de adjudicação são referidos?',
  'Quem é a entidade adjudicante?',
  'O procedimento tem lotes?',
  'Qual é o local de execução do contrato?',
  'Que habilitações são exigidas?',
]
const FALLBACK_BOOTSTRAP = {
  api_version: 'offline',
  product_title: 'RAG para análise de contratos e avisos públicos',
  question_suggestions: FALLBACK_SUGGESTIONS,
  categories: FALLBACK_CATEGORIES,
  default_category: 'todos',
  sessions_enabled: true,
  rag_backend_ready: false,
  rag_backend_error: null,
  recommended_frontend: 'react',
}

// Mapa de labels PT para campos estruturados
const STRUCTURED_LABELS = {
  entidade: 'Entidade adjudicante',
  objeto: 'Objeto / designação',
  prazos: 'Prazos',
  valor: 'Valor / preço base',
  criterios: 'Critérios de adjudicação',
  caucao: 'Caução / garantia',
  cpv: 'CPV',
  lotes: 'Procedimento com lotes',
  local: 'Local de execução',
  requisitos: 'Habilitações / requisitos',
  referencias_relevantes: 'Referências',
}

function classNames(...items) {
  return items.filter(Boolean).join(' ')
}

function sameNormalizedLabel(a, b) {
  return String(a || '').trim().toLowerCase() === String(b || '').trim().toLowerCase()
}

function formatCitationCountLabel(count) {
  const safeCount = Number(count || 0)
  return `${safeCount} ${safeCount === 1 ? 'citação' : 'citações'}`
}

function formatDateTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('pt-PT', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date)
}

function trimText(value, maxLength = 140) {
  const text = String(value || '').replace(/\s+/g, ' ').trim()
  if (!text) return 'Sem conteúdo.'
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text
}

const QUESTION_STOPWORDS = new Set([
  'a','as','o','os','de','do','da','dos','das','e','ou','para','por','com','sem','em','no','na','nos','nas',
  'um','uma','uns','umas','qual','quais','que','é','sao','são','ha','há','existe','existem','ser','sao','foi','referido','referidos','referida','referidas','indicado','indicados','indicada','indicadas',
])

const QUESTION_TOKEN_REPLACEMENTS = {
  criterios: 'criterio',
  critério: 'criterio',
  critérios: 'criterio',
  adjudicacao: 'adjudicacao',
  adjudicação: 'adjudicacao',
  propostas: 'proposta',
  candidaturas: 'candidatura',
  lotes: 'lote',
  campos: 'campo',
  documentos: 'documento',
}

function normalizeQuestionKey(value) {
  return String(value || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[?!.:,;()\[\]{}]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function questionSignature(value) {
  const normalized = normalizeQuestionKey(value)
  if (!normalized) return ''
  const tokens = normalized
    .split(' ')
    .map((token) => QUESTION_TOKEN_REPLACEMENTS[token] || token)
    .map((token) => {
      if (token.length > 4 && token.endsWith('s')) return token.slice(0, -1)
      return token
    })
    .filter((token) => token && !QUESTION_STOPWORDS.has(token) && token.length > 2)
  return tokens.sort().join(' ')
}

function filterPendingSuggestedQuestions(suggestions, askedQuestions) {
  if (!suggestions?.length) return []
  const askedSigs = new Set(askedQuestions.map(questionSignature).filter(Boolean))
  return suggestions.filter((q) => {
    const sig = questionSignature(q)
    return sig && !askedSigs.has(sig)
  })
}

function normalizeErrorMessage(err) {
  if (!err) return 'Erro desconhecido.'
  if (typeof err === 'string') return err
  if (err?.detail) return String(err.detail)
  if (err?.message) return String(err.message)
  return 'Erro desconhecido.'
}

async function fetchJSON(path, options = {}) {
  const url = `${API_BASE_URL}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = body?.detail || detail
    } catch (_) {}
    throw new Error(detail)
  }
  return res.json()
}

function buildAssistantPayload(message, index) {
  const qa = message?.qa_result || {}
  return {
    id: `msg-${index}`,
    createdAt: message?.created_at || null,
    preview: trimText(message?.content || '', 90),
    answer: qa.answer || null,
    confidence: qa.confidence || null,
    sources: (qa.sources || qa.sources_grouped || []),
    structured_data: qa.structured_data || {},
    follow_up_questions: qa.follow_up_questions || [],
  }
}

function getAssistantPayloads(chat) {
  if (!chat?.messages?.length) return []
  return chat.messages
    .map((msg, idx) => (msg?.role === 'assistant' ? buildAssistantPayload(msg, idx) : null))
    .filter(Boolean)
}

// ─── Markdown renderer ──────────────────────────────────────────────────────

function MarkdownBlock({ text }) {
  if (!text) return null
  const lines = text.split('\n')
  const nodes = []
  let listItems = []
  let key = 0

  function flushList(reason) {
    if (!listItems.length) return
    if (reason === 'ul') nodes.push(<ul key={`ul-${key++}`}>{listItems}</ul>)
    else nodes.push(<ul key={`ul-${key++}`}>{listItems}</ul>)
    listItems = []
  }

  for (const line of lines) {
    // heading
    const h2 = line.match(/^## (.+)/)
    if (h2) {
      flushList('end')
      nodes.push(<h4 key={key++} className="md-heading">{renderInline(h2[1])}</h4>)
      continue
    }
    // bullet
    const bullet = line.match(/^[-*•] (.+)/)
    if (bullet) {
      listItems.push(<li key={key++}>{renderInline(bullet[1])}</li>)
      continue
    }
    // numbered list
    const numbered = line.match(/^\d+\. (.+)/)
    if (numbered) {
      listItems.push(<li key={key++}>{renderInline(numbered[1])}</li>)
      continue
    }
    flushList('end')
    if (!line.trim()) {
      nodes.push(<div key={key++} className="md-spacer" />)
    } else {
      nodes.push(<p key={key++} className="md-para">{renderInline(line)}</p>)
    }
  }
  flushList('end')

  return <div className="markdown-content">{nodes}</div>
}

function renderInline(text) {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[\d+\])/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i}>{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={i}>{part.slice(1, -1)}</em>
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} className="md-code">{part.slice(1, -1)}</code>
    }
    if (/^\[\d+\]$/.test(part)) {
      return <sup key={i} className="citation-ref">{part}</sup>
    }
    return part
  })
}

// ─── Components ─────────────────────────────────────────────────────────────

function ConfidenceBadge({ confidence }) {
  const label = confidence?.label || 'desconhecida'
  return (
    <span className={classNames('confidence-badge', `confidence-${label}`)}>
      Confiança: {label}
      {typeof confidence?.score === 'number' ? ` (${Math.round(confidence.score * 100)}%)` : ''}
    </span>
  )
}

function ChatItem({ chat, active, deleting, onSelect, onDelete }) {
  return (
    <div className={classNames('chat-item-shell', active && 'chat-item-shell-active')}>
      <button
        className={classNames('chat-item', active && 'chat-item-active')}
        onClick={() => onSelect(chat.id)}
        title={chat.title || 'Novo chat'}
      >
        <div className="chat-item-row">
          <div className="chat-item-title" title={chat.title || 'Novo chat'}>{chat.title || 'Novo chat'}</div>
          <div className="chat-item-actions">
            <span className="chat-item-badge">{chat.messages_count || 0}</span>
          </div>
        </div>
        <div className="chat-item-meta" title={chat.last_message_preview || 'Sem mensagens ainda.'}>
          {chat.last_message_preview || 'Sem mensagens ainda.'}
        </div>
        <div className="chat-item-date">{formatDateTime(chat.updated_at)}</div>
      </button>
      <button
        className="chat-delete-hitbox"
        onClick={(event) => { event.stopPropagation(); onDelete(chat.id) }}
        disabled={deleting}
        title="Apagar chat"
        aria-label="Apagar chat"
      >×</button>
    </div>
  )
}

function ResponsePicker({ payloads, selectedId, onSelect }) {
  if (!payloads.length) {
    return <div className="empty-panel empty-panel-compact">Ainda não há respostas neste chat.</div>
  }
  return (
    <div className="response-picker-list">
      {payloads.map((payload, index) => (
        <button
          key={payload.id}
          className={classNames('response-picker-item', payload.id === selectedId && 'response-picker-item-active')}
          onClick={() => onSelect(payload.id)}
        >
          <div className="response-picker-top">
            <strong>Resposta {payloads.length - index}</strong>
            <span>{formatDateTime(payload.createdAt)}</span>
          </div>
          <div className="response-picker-preview" title={payload.preview}>{payload.preview}</div>
        </button>
      ))}
    </div>
  )
}

function SourceCard({ source }) {
  const meta = [source.document_type, source.entity, source.pages_label || source.primary_locator].filter(Boolean)
  const citations = source.citations || []
  const sourceTitle = source.title || source.source_id || 'Fonte'
  const showSourceIdBadge = source.source_id && !sameNormalizedLabel(source.source_id, sourceTitle)

  return (
    <article className="source-card source-card-compact">
      <div className="source-card-top source-card-top-compact">
        <div className="source-card-main">
          <div className="source-card-title-row">
            <h4>{sourceTitle}</h4>
            {showSourceIdBadge ? <span className="source-inline-badge">{source.source_id}</span> : null}
          </div>
          <p className="source-card-meta">{meta.join(' • ') || 'Sem metadados adicionais'}</p>
        </div>
        <div className="source-card-actions">
          {citations.length ? (
            <span className="source-inline-badge source-inline-badge-count">
              {formatCitationCountLabel(citations.length)}
            </span>
          ) : null}
          {source.source_url ? (
            <a href={source.source_url} target="_blank" rel="noreferrer" className="source-link">
              Abrir
            </a>
          ) : null}
        </div>
      </div>
      {source.primary_excerpt ? (
        <p className="source-excerpt source-excerpt-compact" title={source.primary_excerpt}>
          {source.primary_excerpt}
        </p>
      ) : null}
      {citations.length ? (
        <div className="citation-list citation-list-compact">
          {citations.slice(0, 2).map((citation, index) => (
            <div className="citation-item citation-item-compact" key={`${source.source_id}-${index}`}>
              <div className="citation-locator">{citation.locator || 'Trecho'}</div>
              <div className="citation-excerpt">{citation.excerpt}</div>
            </div>
          ))}
        </div>
      ) : null}
    </article>
  )
}

function renderStructuredValue(key, value) {
  // referencias_relevantes é lista de objetos {citation, summary}
  if (key === 'referencias_relevantes' && Array.isArray(value)) {
    return (
      <ul className="structured-ref-list">
        {value.map((ref, i) => (
          <li key={i}>
            <sup className="citation-ref">{ref.citation || `[${i + 1}]`}</sup>{' '}
            {ref.summary || String(ref)}
          </li>
        ))}
      </ul>
    )
  }
  if (Array.isArray(value)) return value.join(', ')
  return String(value)
}

function StructuredDataPanel({ structuredData }) {
  const entries = Object.entries(structuredData || {}).filter(([, value]) => {
    if (value == null) return false
    if (Array.isArray(value)) return value.length > 0
    if (typeof value === 'string') return value.trim().length > 0
    return true
  })

  if (!entries.length) {
    return <p className="empty-panel">Sem extração estruturada disponível para esta resposta.</p>
  }

  return (
    <div className="structured-grid">
      {entries.map(([key, value]) => (
        <div className="structured-card" key={key}>
          <div className="structured-label">{STRUCTURED_LABELS[key] || key.replace(/_/g, ' ')}</div>
          <div className="structured-value">{renderStructuredValue(key, value)}</div>
        </div>
      ))}
    </div>
  )
}

function ThemeToggle({ theme, onToggle }) {
  return (
    <button className="theme-toggle button" onClick={onToggle} aria-label="Alternar tema" title="Alternar tema">
      <span aria-hidden="true" className="theme-toggle-icon">{theme === 'dark' ? '☀' : '☾'}</span>
    </button>
  )
}

function getAnswerModeText(answer) {
  if (answer?.response_mode === 'llm') return answer?.llm_label || 'LLM (Ollama)'
  if (answer?.response_mode === 'heuristic') return 'Extração direta / heurística'
  if (typeof answer?.used_llm !== 'boolean') return '—'
  return answer.used_llm ? 'LLM (Ollama)' : 'Extração direta / heurística'
}

function FollowUpChips({ questions, onUse }) {
  if (!questions?.length) return null
  return (
    <div className="message-followups">
      <div className="message-followups-label">Sugestões de seguimento</div>
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

function InspectorPanel({ selectedPayload, selectedTab, onChangeTab }) {
  const tabs = [
    { id: 'fontes', label: 'Fontes' },
    { id: 'campos', label: 'Campos' },
    { id: 'metadados', label: 'Metadados' },
  ]

  if (!selectedPayload) {
    return (
      <section className="panel inspector-panel inspector-single-panel">
        <div className="panel-header">
          <h3>Inspeção da resposta</h3>
          <span>—</span>
        </div>
        <div className="empty-panel">Seleciona uma resposta para inspecionar fontes, campos e metadados.</div>
      </section>
    )
  }

  const sources = selectedPayload?.sources || []
  const confidence = selectedPayload?.confidence
  const answer = selectedPayload?.answer

  return (
    <section className="panel inspector-panel inspector-single-panel">
      <div className="panel-header">
        <h3>Inspeção</h3>
        <div className="panel-header-actions">
          {confidence ? <ConfidenceBadge confidence={confidence} /> : null}
        </div>
      </div>

      <div className="tab-row">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={classNames('tab-button', selectedTab === tab.id && 'tab-button-active')}
            onClick={() => onChangeTab(tab.id)}
          >
            {tab.label}
            {tab.id === 'fontes' && sources.length ? (
              <span className="tab-count">{sources.length}</span>
            ) : null}
          </button>
        ))}
      </div>

      {selectedTab === 'fontes' ? (
        sources.length ? (
          <div className="source-list">
            {sources.map((source) => (
              <SourceCard key={`${source.source_id}-${source.primary_locator || ''}`} source={source} />
            ))}
          </div>
        ) : (
          <div className="empty-panel">Sem fontes identificadas para esta resposta.</div>
        )
      ) : null}

      {selectedTab === 'campos' ? (
        <StructuredDataPanel structuredData={selectedPayload?.structured_data || {}} />
      ) : null}

      {selectedTab === 'metadados' ? (
        <div className="meta-list meta-list-compact">
          <div className="meta-grid">
            <div className="meta-item">
              <div className="meta-label">Intenção</div>
              <div className="meta-value">{answer?.intent || '—'}</div>
            </div>
            <div className="meta-item">
              <div className="meta-label">Fontes citadas</div>
              <div className="meta-value">{answer?.citations_count ?? '—'}</div>
            </div>
            <div className="meta-item">
              <div className="meta-label">Tempo</div>
              <div className="meta-value">{answer?.elapsed_ms ? `${answer.elapsed_ms} ms` : '—'}</div>
            </div>
            <div className="meta-item">
              <div className="meta-label">Modo</div>
              <div className="meta-value">{getAnswerModeText(answer)}</div>
            </div>
          </div>
          {answer?.retrieval_query ? (
            <div className="meta-query-box">
              <div className="meta-label">Consulta RAG</div>
              <div className="meta-query">{trimText(answer.retrieval_query, 200)}</div>
            </div>
          ) : null}
          {confidence?.reasons?.length ? (
            <div className="meta-query-box">
              <div className="meta-label">Suporte da confiança</div>
              <ul className="reason-list">
                {confidence.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}

// ─── App ─────────────────────────────────────────────────────────────────────

function App() {
  const [bootstrap, setBootstrap] = useState(FALLBACK_BOOTSTRAP)
  const [apiOnline, setApiOnline] = useState(false)
  const [chats, setChats] = useState([])
  const [activeChatId, setActiveChatId] = useState(null)
  const [activeChat, setActiveChat] = useState(null)
  const [selectedResponseId, setSelectedResponseId] = useState(null)
  const [selectedInspectorTab, setSelectedInspectorTab] = useState('fontes')
  const [draft, setDraft] = useState('')
  const [category, setCategory] = useState('todos')
  const [topK, setTopK] = useState(4)
  const [theme, setTheme] = useState(() => window.localStorage.getItem('rag-theme') || 'dark')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [sendingQuestion, setSendingQuestion] = useState('')
  const [deletingChatId, setDeletingChatId] = useState(null)
  const [copiedAnswerId, setCopiedAnswerId] = useState(null)
  const [showAllSuggestions, setShowAllSuggestions] = useState(false)
  const [error, setError] = useState('')
  const messageListRef = useRef(null)
  const composerRef = useRef(null)
  const previousActiveChatIdRef = useRef(null)
  const previousMessageCountRef = useRef(0)
  const sendLockRef = useRef(false)
  const lastSubmissionRef = useRef({ signature: '', ts: 0 })

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    window.localStorage.setItem('rag-theme', theme)
  }, [theme])

  const loadBootstrap = useCallback(async () => {
    const data = await fetchJSON('/bootstrap')
    setBootstrap({
      ...FALLBACK_BOOTSTRAP,
      ...data,
      question_suggestions: data?.question_suggestions?.length ? data.question_suggestions : FALLBACK_SUGGESTIONS,
    })
    setCategory(data.default_category || 'todos')
    setApiOnline(true)
    return data
  }, [])

  const loadChat = useCallback(async (chatId) => {
    if (!chatId) return
    const data = await fetchJSON(`/sessions/${chatId}`)
    setActiveChat(data)
    setActiveChatId(chatId)
  }, [])

  const loadChats = useCallback(async (preferredChatId = null) => {
    const data = await fetchJSON('/sessions')
    setChats(data)
    const nextId = preferredChatId || activeChatId || data[0]?.id || null
    if (nextId) {
      setActiveChatId(nextId)
      await loadChat(nextId)
    } else {
      setActiveChatId(null)
      setActiveChat(null)
    }
  }, [activeChatId, loadChat])

  const boot = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      await loadBootstrap()
      await loadChats()
    } catch (err) {
      setBootstrap(FALLBACK_BOOTSTRAP)
      setApiOnline(false)
      setChats([])
      setActiveChatId(null)
      setActiveChat(null)
      setError(normalizeErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [loadBootstrap, loadChats])

  useEffect(() => { boot() }, [boot])

  const assistantPayloads = useMemo(() => getAssistantPayloads(activeChat), [activeChat])

  const askedQuestions = useMemo(() => {
    return (activeChat?.messages || [])
      .filter((m) => m?.role === 'user' && normalizeQuestionKey(m.content))
      .map((m) => String(m.content || '').trim())
  }, [activeChat])

  useEffect(() => { setShowAllSuggestions(false) }, [activeChatId])

  useEffect(() => {
    if (!assistantPayloads.length) { setSelectedResponseId(null); return }
    const hasCurrent = assistantPayloads.some((p) => p.id === selectedResponseId)
    if (!hasCurrent) setSelectedResponseId(assistantPayloads[assistantPayloads.length - 1].id)
  }, [assistantPayloads, selectedResponseId])

  const selectedPayload = useMemo(() => {
    if (!assistantPayloads.length) return null
    return assistantPayloads.find((p) => p.id === selectedResponseId) || assistantPayloads[assistantPayloads.length - 1]
  }, [assistantPayloads, selectedResponseId])

  const latestAssistantPayloadId = assistantPayloads.length ? assistantPayloads[assistantPayloads.length - 1].id : null

  const categories = bootstrap?.categories || FALLBACK_CATEGORIES
  const chatsCountLabel = `${chats.length} ${chats.length === 1 ? 'chat' : 'chats'}`
  const responsesCountLabel = `${assistantPayloads.length} ${assistantPayloads.length === 1 ? 'resposta' : 'respostas'}`
  const baseSuggestions = bootstrap?.question_suggestions?.length ? bootstrap.question_suggestions : FALLBACK_SUGGESTIONS
  const pendingSuggestions = useMemo(() => filterPendingSuggestedQuestions(baseSuggestions, askedQuestions), [baseSuggestions, askedQuestions])
  const hasDenseHistory = (activeChat?.messages?.length || 0) >= 6
  const compactSuggestionLimit = hasDenseHistory ? 3 : 6
  const visibleSuggestions = showAllSuggestions ? pendingSuggestions : pendingSuggestions.slice(0, compactSuggestionLimit)
  const hasHiddenSuggestions = pendingSuggestions.length > visibleSuggestions.length
  const askDisabled = sending || !draft.trim() || !apiOnline || !bootstrap?.rag_backend_ready

  // Auto-resize textarea
  useEffect(() => {
    const textarea = composerRef.current
    if (!textarea) return
    textarea.style.height = '0px'
    const nextHeight = Math.min(Math.max(textarea.scrollHeight, 112), 240)
    textarea.style.height = `${nextHeight}px`
  }, [draft])

  // Auto-scroll on new messages
  useEffect(() => {
    const container = messageListRef.current
    const messageCount = activeChat?.messages?.length || 0
    if (!container) {
      previousActiveChatIdRef.current = activeChatId
      previousMessageCountRef.current = messageCount
      return
    }
    const chatChanged = previousActiveChatIdRef.current !== activeChatId
    const messageCountIncreased = messageCount > previousMessageCountRef.current
    if (chatChanged || messageCountIncreased) {
      window.requestAnimationFrame(() => {
        container.scrollTo({ top: container.scrollHeight, behavior: chatChanged ? 'auto' : 'smooth' })
      })
    }
    previousActiveChatIdRef.current = activeChatId
    previousMessageCountRef.current = messageCount
  }, [activeChatId, activeChat?.messages?.length, sending])

  const handleUseFollowUp = useCallback((question) => {
    setDraft(question)
    window.requestAnimationFrame(() => {
      const composer = composerRef.current
      if (composer) { composer.focus(); composer.setSelectionRange(question.length, question.length) }
    })
  }, [])

  async function handleCopyAnswer(answerId, markdown) {
    try {
      await navigator.clipboard.writeText(markdown || '')
      setCopiedAnswerId(answerId)
      window.setTimeout(() => setCopiedAnswerId((c) => (c === answerId ? null : c)), 1600)
    } catch (_) {
      setError('Não foi possível copiar a resposta.')
    }
  }

  async function handleSelectChat(chatId) {
    setError('')
    try { await loadChat(chatId) } catch (err) { setError(normalizeErrorMessage(err)) }
  }

  async function createChat() {
    if (!apiOnline) {
      setError(`API FastAPI não acessível em ${API_BASE_URL}. Arranca primeiro: uvicorn api:app --reload`)
      return null
    }
    try {
      const data = await fetchJSON('/sessions', { method: 'POST', body: JSON.stringify({ title: 'Novo chat' }) })
      setChats((c) => [{ id: data.id, title: data.title, created_at: data.created_at, updated_at: data.updated_at, messages_count: 0, last_message_preview: null }, ...c])
      setActiveChatId(data.id)
      setActiveChat(data)
      setSelectedResponseId(null)
      setError('')
      return data
    } catch (err) { setError(normalizeErrorMessage(err)); return null }
  }

  async function handleDeleteChat(chatId) {
    if (!apiOnline || deletingChatId) return
    const chat = chats.find((c) => c.id === chatId)
    const label = chat?.title || 'este chat'
    if (!window.confirm(`Apagar "${label}"?`)) return
    setDeletingChatId(chatId)
    setError('')
    try {
      await fetchJSON(`/sessions/${chatId}`, { method: 'DELETE' })
      const remaining = chats.filter((c) => c.id !== chatId)
      setChats(remaining)
      if (activeChatId === chatId) {
        const next = remaining[0]
        if (next) { await loadChat(next.id) } else { setActiveChatId(null); setActiveChat(null) }
      }
    } catch (err) { setError(normalizeErrorMessage(err)) }
    finally { setDeletingChatId(null) }
  }

  async function handleAsk(questionOverride) {
    const clean = (questionOverride || draft).replace(/\s+/g, ' ').trim()
    if (!clean) return

    const now = Date.now()
    const signature = questionSignature(clean)
    const last = lastSubmissionRef.current
    if (sendLockRef.current || (last.signature === signature && now - last.ts < 1500)) return

    if (!apiOnline) {
      setError(`API FastAPI não acessível em ${API_BASE_URL}. Arranca primeiro: uvicorn api:app --reload`)
      return
    }
    if (!bootstrap?.rag_backend_ready) {
      setError('API online, mas backend RAG indisponível. Verifica /health e o índice vetorial.')
      return
    }

    sendLockRef.current = true
    lastSubmissionRef.current = { signature, ts: now }

    let chatId = activeChatId
    if (!chatId) {
      const chat = await createChat()
      chatId = chat?.id || null
      if (!chatId) { sendLockRef.current = false; return }
    }

    setSending(true)
    setSendingQuestion(clean)
    setError('')
    try {
      const data = await fetchJSON(`/sessions/${chatId}/ask`, {
        method: 'POST',
        body: JSON.stringify({ query: clean, category, top_k: topK }),
      })
      setActiveChat(data.session)
      setDraft('')
      await loadChats(chatId)
    } catch (err) {
      setError(normalizeErrorMessage(err))
    } finally {
      setSending(false)
      setSendingQuestion('')
      sendLockRef.current = false
    }
  }

  function handleSubmit(event) {
    event.preventDefault()
    handleAsk()
  }

  return (
    <div className="app-shell">
      {/* ── Sidebar ── */}
      <aside className="sidebar panel">
        <div className="sidebar-top">
          <div>
            <h2>Chats</h2>
            <div className="sidebar-subtitle">{chatsCountLabel}</div>
          </div>
          <button className="button button-primary sidebar-new-button" onClick={createChat} disabled={!apiOnline}>
            + Novo
          </button>
        </div>
        <div className="chat-list">
          {chats.length ? (
            chats.map((chat) => (
              <ChatItem
                key={chat.id}
                chat={chat}
                active={chat.id === activeChatId}
                deleting={deletingChatId === chat.id}
                onSelect={handleSelectChat}
                onDelete={handleDeleteChat}
              />
            ))
          ) : (
            <div className="empty-panel empty-panel-compact">
              {apiOnline ? 'Ainda não existem chats.' : 'Sem ligação à API.'}
            </div>
          )}
        </div>
      </aside>

      {/* ── Main column ── */}
      <main className="main-column">
        <header className="hero panel">
          <div>
            <h1>RAG — Contratos e Avisos Públicos</h1>
            <p>
              Perguntas sobre prazo, valor base, entidade adjudicante, critérios, caução,
              CPV, lotes e outros campos, com respostas ancoradas em fontes documentais.
            </p>
          </div>
          <div className="hero-actions">
            <ThemeToggle theme={theme} onToggle={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))} />
          </div>
        </header>

        {!apiOnline ? (
          <section className="notice-banner notice-warning panel">
            <div>
              <strong>API FastAPI offline.</strong> Arranca primeiro: <code>uvicorn api:app --reload</code>
            </div>
            <button className="button" onClick={boot}>Tentar novamente</button>
          </section>
        ) : !bootstrap?.rag_backend_ready ? (
          <section className="notice-banner notice-warning panel">
            <div>
              <strong>API online, mas backend RAG indisponível.</strong>{' '}
              {bootstrap?.rag_backend_error ? trimText(bootstrap.rag_backend_error, 200) : 'Confirma o índice vetorial (scripts/ingest.py).'}
            </div>
            <button className="button" onClick={boot}>Atualizar estado</button>
          </section>
        ) : null}

        {/* Toolbar */}
        <section className="toolbar panel toolbar-compact">
          <div className="toolbar-group">
            <label>
              Categoria
              <select value={category} onChange={(e) => setCategory(e.target.value)}>
                {categories.map((item) => (
                  <option key={item.id} value={item.id}>{item.label}</option>
                ))}
              </select>
            </label>
            <label>
              Top K
              <input
                type="number" min="1" max="12" value={topK}
                onChange={(e) => setTopK(Number(e.target.value) || 4)}
              />
            </label>
          </div>
          <div className="status-strip">
            <span className={classNames('status-pill', apiOnline ? 'status-ok' : 'status-warn')}>
              API: {apiOnline ? 'online' : 'offline'}
            </span>
            <span className={classNames('status-pill', bootstrap?.rag_backend_ready ? 'status-ok' : 'status-warn')}>
              RAG: {bootstrap?.rag_backend_ready ? 'pronto' : 'indisponível'}
            </span>
          </div>
        </section>

        {/* Sugestões */}
        <section className={classNames('suggestions panel', hasDenseHistory && 'suggestions-compact')}>
          <div className="panel-header panel-header-compact">
            <h3>Perguntas sugeridas</h3>
            <div className="panel-header-actions">
              {hasHiddenSuggestions ? (
                <button type="button" className="text-button" onClick={() => setShowAllSuggestions((v) => !v)}>
                  {showAllSuggestions ? 'Ver menos' : 'Ver mais'}
                </button>
              ) : null}
            </div>
          </div>
          {visibleSuggestions.length ? (
            <div className="chip-row">
              {visibleSuggestions.map((q) => (
                <button
                  key={q} className="chip"
                  onClick={() => handleAsk(q)}
                  disabled={!apiOnline || !bootstrap?.rag_backend_ready || sending}
                >
                  {q}
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-panel empty-panel-compact">Não há novas sugestões.</div>
          )}
        </section>

        {/* Chat */}
        <section className="chat panel chat-panel">
          <div className="panel-header chat-panel-header">
            <h3>
              {activeChat?.title && !['Novo chat', 'Nova sessão'].includes(activeChat.title)
                ? activeChat.title
                : 'Chat'}
            </h3>
            <span>
              {activeChat?.messages?.length
                ? `${activeChat.messages.length} ${activeChat.messages.length === 1 ? 'mensagem' : 'mensagens'}`
                : 'Sem mensagens'}
            </span>
          </div>

          {loading ? <div className="empty-panel">A carregar…</div> : null}
          {error ? <div className="error-banner">{error}</div> : null}

          <div
            ref={messageListRef}
            className={classNames('message-list', 'message-list-expanded', sending && 'message-list-sending')}
            aria-live={sending ? 'polite' : 'off'}
          >
            {activeChat?.messages?.length ? (
              activeChat.messages.map((message, index) => {
                const payload = message.role === 'assistant' ? buildAssistantPayload(message, index) : null
                const isSelected = payload?.id && payload.id === selectedPayload?.id
                const isAssistant = message.role === 'assistant'
                return (
                  <article
                    key={`${message.role}-${index}`}
                    className={classNames(
                      'message-card',
                      `message-${message.role}`,
                      payload && 'message-clickable',
                      isSelected && 'message-selected',
                    )}
                    onClick={payload ? () => { setSelectedResponseId(payload.id); setSelectedInspectorTab('fontes') } : undefined}
                  >
                    <div className="message-shell">
                      <div className={classNames('message-avatar', isAssistant ? 'message-avatar-assistant' : 'message-avatar-user')}>
                        {isAssistant ? '⚖' : 'Tu'}
                      </div>
                      <div className="message-body">
                        <div className="message-header-row">
                          <div className="message-role">{isAssistant ? 'Assistente' : 'Pergunta'}</div>
                          <div className="message-actions">
                            {isSelected ? <span className="message-tag">Selecionada</span> : null}
                            {payload ? (
                              <button
                                type="button" className="message-copy-button"
                                onClick={(e) => { e.stopPropagation(); handleCopyAnswer(payload.id, payload.answer?.markdown || message.content || '') }}
                                title="Copiar resposta"
                              >
                                {copiedAnswerId === payload.id ? '✓ Copiado' : 'Copiar'}
                              </button>
                            ) : null}
                          </div>
                        </div>
                        {isAssistant ? (
                          <>
                            <MarkdownBlock text={message.content} />
                            {payload?.id === latestAssistantPayloadId ? (
                              <FollowUpChips
                                questions={filterPendingSuggestedQuestions(payload?.follow_up_questions || [], askedQuestions)}
                                onUse={handleUseFollowUp}
                              />
                            ) : null}
                          </>
                        ) : (
                          <div className="message-content">{message.content}</div>
                        )}
                      </div>
                    </div>
                  </article>
                )
              })
            ) : (
              <div className="empty-panel">
                {loading ? '' : apiOnline ? 'Envia uma pergunta para começar.' : 'Liga a API para criar chats.'}
              </div>
            )}

            {sending && sendingQuestion ? (
              <article className="message-card message-assistant message-pending" role="status" aria-live="polite">
                <div className="message-shell">
                  <div className="message-avatar message-avatar-assistant">⚖</div>
                  <div className="message-body">
                    <div className="message-header-row">
                      <div className="message-role">Assistente</div>
                      <div className="message-actions">
                        <span className="message-tag message-tag-live">A responder…</span>
                      </div>
                    </div>
                    <div className="message-content pending-copy">
                      A analisar: <strong>{sendingQuestion}</strong>
                    </div>
                    <div className="pending-loader" aria-hidden="true">
                      <span className="pending-dot"></span>
                      <span className="pending-dot"></span>
                      <span className="pending-dot"></span>
                    </div>
                  </div>
                </div>
              </article>
            ) : null}
          </div>

          {/* Composer */}
          <div className="composer-shell">
            <form className={classNames('composer', sending && 'composer-sending')} onSubmit={handleSubmit}>
              <textarea
                ref={composerRef}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAsk() }
                }}
                placeholder={sending ? 'A aguardar resposta…' : 'Ex.: Qual é o prazo para apresentação das propostas?'}
                rows={3}
                disabled={sending}
              />
              <div className="composer-actions">
                <div className="composer-feedback">
                  <span className={classNames('composer-status-badge', sending && 'composer-status-badge-live')}>
                    {sending ? 'A responder…' : !apiOnline ? 'API offline' : !bootstrap?.rag_backend_ready ? 'Backend indisponível' : 'Pronto'}
                  </span>
                  <span className="composer-hint">
                    {!apiOnline ? 'Sem ligação à API.'
                      : !bootstrap?.rag_backend_ready ? 'Índice vetorial indisponível.'
                      : sending ? 'A aguardar resposta do backend…'
                      : 'Enter envia • Shift+Enter nova linha.'}
                  </span>
                </div>
                <button className="button button-primary" type="submit" disabled={askDisabled}>
                  {sending ? 'A responder…' : !apiOnline ? 'API offline' : !bootstrap?.rag_backend_ready ? 'Indisponível' : 'Perguntar'}
                </button>
              </div>
            </form>
          </div>
        </section>
      </main>

      {/* ── Inspector column ── */}
      <aside className="inspector-column">
        <section className="panel inspector-panel">
          <div className="panel-header">
            <h3>Respostas</h3>
            <span>{responsesCountLabel}</span>
          </div>
          <ResponsePicker
            payloads={[...assistantPayloads].reverse()}
            selectedId={selectedResponseId}
            onSelect={(id) => { setSelectedResponseId(id); setSelectedInspectorTab('fontes') }}
          />
        </section>

        <InspectorPanel
          selectedPayload={selectedPayload}
          selectedTab={selectedInspectorTab}
          onChangeTab={setSelectedInspectorTab}
        />
      </aside>
    </div>
  )
}

export default App
