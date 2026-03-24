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

  const unique = [...new Set(tokens)].sort()
  return unique.join('|')
}

function areQuestionsEquivalent(a, b) {
  const sigA = questionSignature(a)
  const sigB = questionSignature(b)
  if (!sigA || !sigB) return false
  if (sigA === sigB) return true

  const setA = new Set(sigA.split('|'))
  const setB = new Set(sigB.split('|'))
  const intersection = [...setA].filter((token) => setB.has(token)).length
  const union = new Set([...setA, ...setB]).size
  return union > 0 && intersection / union >= 0.75
}

function filterPendingSuggestedQuestions(questions, askedQuestions) {
  const kept = []
  return (questions || []).filter((question) => {
    const normalized = normalizeQuestionKey(question)
    if (!normalized) return false
    if ((askedQuestions || []).some((asked) => areQuestionsEquivalent(question, asked))) return false
    if (kept.some((keptQuestion) => areQuestionsEquivalent(question, keptQuestion))) return false
    kept.push(question)
    return true
  })
}

function normalizeErrorMessage(error) {
  const detail = String(error?.message || '').trim()
  if (!detail || detail === 'Failed to fetch') {
    return `Não foi possível ligar à API em ${API_BASE_URL}. Arranca primeiro: uvicorn api:app --reload`
  }
  return detail
}

async function fetchJSON(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })

  if (response.status === 204) {
    return null
  }

  const data = await response
    .json()
    .catch(() => ({ detail: 'Resposta inválida do servidor.' }))

  if (!response.ok) {
    const detail = typeof data?.detail === 'string' ? data.detail : 'Pedido falhou.'
    throw new Error(detail)
  }

  return data
}

function buildAssistantPayload(message, index) {
  if (!message?.qa_result) return null
  return {
    id: message.id || `assistant-${index}`,
    messageIndex: index,
    createdAt: message.created_at || null,
    preview: trimText(message.content || message.qa_result?.answer?.markdown || ''),
    answer: message.qa_result.answer || {
      markdown: message.content || '',
      intent: message.qa_result.intent || 'desconhecido',
      retrieval_query: message.qa_result.retrieval_query || '',
      elapsed_ms: message.qa_result.elapsed_ms || 0,
      citations_count: message.qa_result.citations_count || 0,
      used_llm: Boolean(message.qa_result.used_llm),
      response_mode: message.qa_result.response_mode || (message.qa_result.used_llm ? 'llm' : 'heuristic'),
      llm_label: message.qa_result.llm_label || null,
    },
    confidence: message.qa_result.confidence || {
      label: message.qa_result.confidence_label || 'desconhecida',
      score: Number(message.qa_result.confidence_score || 0),
      reasons: message.qa_result.confidence_reasons || [],
    },
    sources: message.qa_result.sources || message.qa_result.sources_grouped || [],
    structured_data: message.qa_result.structured_data || {},
    follow_up_questions: message.qa_result.follow_up_questions || [],
  }
}

function getAssistantPayloads(chat) {
  if (!chat?.messages?.length) return []
  return chat.messages
    .map((message, index) => {
      if (message?.role !== 'assistant') return null
      return buildAssistantPayload(message, index)
    })
    .filter(Boolean)
}

function MarkdownInline({ text }) {
  const normalized = String(text || '')
  const parts = normalized.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((part, index) => {
    if (/^\*\*[^*]+\*\*$/.test(part)) {
      return <strong key={index}>{part.slice(2, -2)}</strong>
    }
    return <React.Fragment key={index}>{part}</React.Fragment>
  })
}

function MarkdownBlock({ text }) {
  const lines = String(text || '').replace(/\r/g, '').split('\n')
  const nodes = []
  let listItems = []

  function flushList(keyPrefix) {
    if (!listItems.length) return
    nodes.push(
      <ul className="markdown-list" key={`${keyPrefix}-list-${nodes.length}`}>
        {listItems.map((item, index) => (
          <li key={`${keyPrefix}-li-${index}`}><MarkdownInline text={item} /></li>
        ))}
      </ul>,
    )
    listItems = []
  }

  lines.forEach((rawLine, index) => {
    const line = rawLine.trim()

    if (!line) {
      flushList(`line-${index}`)
      return
    }

    if (line.startsWith('- ') || line.startsWith('* ')) {
      listItems.push(line.slice(2))
      return
    }

    flushList(`line-${index}`)

    if (line.startsWith('### ')) {
      nodes.push(<h4 className="markdown-h4" key={`line-${index}`}><MarkdownInline text={line.slice(4)} /></h4>)
      return
    }

    if (line.startsWith('## ')) {
      nodes.push(<h3 className="markdown-h3" key={`line-${index}`}><MarkdownInline text={line.slice(3)} /></h3>)
      return
    }

    if (line.startsWith('# ')) {
      nodes.push(<h2 className="markdown-h2" key={`line-${index}`}><MarkdownInline text={line.slice(2)} /></h2>)
      return
    }

    nodes.push(<p className="markdown-p" key={`line-${index}`}><MarkdownInline text={line} /></p>)
  })

  flushList('end')

  return <div className="markdown-content">{nodes}</div>
}

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
      <button className={classNames('chat-item', active && 'chat-item-active')} onClick={() => onSelect(chat.id)} title={chat.title || 'Novo chat'}>
        <div className="chat-item-row">
          <div className="chat-item-title" title={chat.title || 'Novo chat'}>{chat.title || 'Novo chat'}</div>
          <div className="chat-item-actions">
            <span className="chat-item-badge">{chat.messages_count || 0}</span>
            <span className="chat-delete-button" aria-hidden="true">×</span>
          </div>
        </div>
        <div className="chat-item-meta" title={chat.last_message_preview || 'Sem mensagens ainda.'}>{chat.last_message_preview || 'Sem mensagens ainda.'}</div>
        <div className="chat-item-date">{formatDateTime(chat.updated_at)}</div>
      </button>
      <button
        className="chat-delete-hitbox"
        onClick={(event) => {
          event.stopPropagation()
          onDelete(chat.id)
        }}
        disabled={deleting}
        title="Apagar chat"
        aria-label="Apagar chat"
      />
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
          {citations.length ? <span className="source-inline-badge source-inline-badge-count">{formatCitationCountLabel(citations.length)}</span> : null}
          {source.source_url ? (
            <a href={source.source_url} target="_blank" rel="noreferrer" className="source-link">
              Abrir
            </a>
          ) : null}
        </div>
      </div>
      {source.primary_excerpt ? <p className="source-excerpt source-excerpt-compact" title={source.primary_excerpt}>{source.primary_excerpt}</p> : null}
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
          <div className="structured-label">{key.replaceAll('_', ' ')}</div>
          <div className="structured-value">
            {Array.isArray(value) ? value.join(', ') : String(value)}
          </div>
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
  if (answer?.response_mode === 'llm') return answer?.llm_label || 'LLM'
  if (answer?.response_mode === 'heuristic') return 'Extração direta / heurística'
  if (typeof answer?.used_llm !== 'boolean') return '—'
  return answer.used_llm ? 'LLM' : 'Extração direta / heurística'
}

function FollowUpChips({ questions, onUse }) {
  if (!questions?.length) return null

  return (
    <div className="message-followups">
      <div className="message-followups-label">Perguntas sugeridas</div>
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

function InspectorTabs({ selectedPayload, selectedTab, onChangeTab }) {
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
          <span>Estado atual</span>
        </div>
        <div className="empty-panel">
Seleciona uma resposta para inspeção.
        </div>
      </section>
    )
  }

  return (
    <section className="panel inspector-panel inspector-single-panel">
      <div className="panel-header">
        <h3>Inspeção da resposta</h3>
        <span>{formatDateTime(selectedPayload.createdAt)}</span>
      </div>

      <div className="tab-row">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={classNames('tab-button', selectedTab === tab.id && 'tab-button-active')}
            onClick={() => onChangeTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {selectedTab === 'fontes' ? (
        selectedPayload?.sources?.length ? (
          <div className="source-list">
            {selectedPayload.sources.map((source) => (
              <SourceCard key={`${source.source_id}-${source.primary_locator || ''}`} source={source} />
            ))}
          </div>
        ) : (
          <div className="empty-panel">As fontes da resposta selecionada aparecem aqui.</div>
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
              <div className="meta-value">{selectedPayload?.answer?.intent || '—'}</div>
            </div>
            <div className="meta-item">
              <div className="meta-label">Fontes citadas</div>
              <div className="meta-value">{selectedPayload?.answer?.citations_count ?? '—'}</div>
            </div>
            <div className="meta-item">
              <div className="meta-label">Tempo</div>
              <div className="meta-value">{selectedPayload?.answer?.elapsed_ms ? `${selectedPayload.answer.elapsed_ms} ms` : '—'}</div>
            </div>
            <div className="meta-item">
              <div className="meta-label">Modo de resposta</div>
              <div className="meta-value">{getAnswerModeText(selectedPayload?.answer)}</div>
            </div>
          </div>
          {selectedPayload?.answer?.retrieval_query ? (
            <div className="meta-query-box">
              <div className="meta-label">Consulta RAG</div>
              <div className="meta-query">{trimText(selectedPayload.answer.retrieval_query, 180)}</div>
            </div>
          ) : null}
          {selectedPayload?.confidence?.reasons?.length ? (
            <div className="meta-query-box">
              <div className="meta-label">Suporte</div>
              <ul className="reason-list">
                {selectedPayload.confidence.reasons.map((reason) => (
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

  useEffect(() => {
    boot()
  }, [boot])

    const assistantPayloads = useMemo(() => getAssistantPayloads(activeChat), [activeChat])

  const askedQuestions = useMemo(() => {
    return (activeChat?.messages || [])
      .filter((message) => message?.role === 'user' && normalizeQuestionKey(message.content))
      .map((message) => String(message.content || '').trim())
  }, [activeChat])

  useEffect(() => {
    setShowAllSuggestions(false)
  }, [activeChatId])

  useEffect(() => {
    if (!assistantPayloads.length) {
      setSelectedResponseId(null)
      return
    }

    const hasCurrent = assistantPayloads.some((payload) => payload.id === selectedResponseId)
    if (!hasCurrent) {
      setSelectedResponseId(assistantPayloads[assistantPayloads.length - 1].id)
    }
  }, [assistantPayloads, selectedResponseId])

  const selectedPayload = useMemo(() => {
    if (!assistantPayloads.length) return null
    return assistantPayloads.find((payload) => payload.id === selectedResponseId) || assistantPayloads[assistantPayloads.length - 1]
  }, [assistantPayloads, selectedResponseId])

  const latestAssistantPayloadId = assistantPayloads.length ? assistantPayloads[assistantPayloads.length - 1].id : null

  const categories = bootstrap?.categories || FALLBACK_CATEGORIES
  const chatsCountLabel = `${chats.length} ${chats.length === 1 ? 'chat disponível' : 'chats'}`
  const responsesCountLabel = `${assistantPayloads.length} ${assistantPayloads.length === 1 ? 'resposta' : 'respostas'}`
  const baseSuggestionQuestions = bootstrap?.question_suggestions?.length ? bootstrap.question_suggestions : FALLBACK_SUGGESTIONS
  const suggestionQuestions = useMemo(() => filterPendingSuggestedQuestions(baseSuggestionQuestions, askedQuestions), [baseSuggestionQuestions, askedQuestions])
  const hasDenseHistory = (activeChat?.messages?.length || 0) >= 6
  const compactSuggestionLimit = hasDenseHistory ? 3 : 6
  const visibleSuggestionQuestions = showAllSuggestions ? suggestionQuestions : suggestionQuestions.slice(0, compactSuggestionLimit)
  const hasHiddenSuggestions = suggestionQuestions.length > visibleSuggestionQuestions.length
  const askDisabled = sending || !draft.trim() || !apiOnline || !bootstrap?.rag_backend_ready


  useEffect(() => {
    const textarea = composerRef.current
    if (!textarea) return
    textarea.style.height = '0px'
    const nextHeight = Math.min(Math.max(textarea.scrollHeight, 112), 240)
    textarea.style.height = `${nextHeight}px`
  }, [draft])

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
        container.scrollTo({
          top: container.scrollHeight,
          behavior: chatChanged ? 'auto' : 'smooth',
        })
      })
    }

    previousActiveChatIdRef.current = activeChatId
    previousMessageCountRef.current = messageCount
  }, [activeChatId, activeChat?.messages?.length, sending])

  const handleUseFollowUp = useCallback((question) => {
    setDraft(question)
    window.requestAnimationFrame(() => {
      const composer = document.querySelector('.composer textarea')
      if (composer) {
        composer.focus()
        composer.setSelectionRange(question.length, question.length)
      }
    })
  }, [])

  async function handleCopyAnswer(answerId, markdown) {
    try {
      await navigator.clipboard.writeText(markdown || '')
      setCopiedAnswerId(answerId)
      window.setTimeout(() => setCopiedAnswerId((current) => (current === answerId ? null : current)), 1600)
    } catch (err) {
      setError('Não foi possível copiar a resposta para a área de transferência.')
    }
  }

  async function handleSelectChat(chatId) {
    setError('')
    try {
      await loadChat(chatId)
    } catch (err) {
      setError(normalizeErrorMessage(err))
    }
  }

  async function createChat() {
    if (!apiOnline) {
      setError(`A API FastAPI não está acessível em ${API_BASE_URL}. Arranca primeiro: uvicorn api:app --reload`)
      return null
    }

    try {
      const data = await fetchJSON('/sessions', {
        method: 'POST',
        body: JSON.stringify({ title: 'Novo chat' }),
      })
      setChats((current) => [
        {
          id: data.id,
          title: data.title,
          created_at: data.created_at,
          updated_at: data.updated_at,
          messages_count: data.messages?.length || 0,
          last_message_preview: null,
        },
        ...current,
      ])
      setActiveChatId(data.id)
      setActiveChat(data)
      setSelectedResponseId(null)
      setError('')
      return data
    } catch (err) {
      setError(normalizeErrorMessage(err))
      return null
    }
  }

  async function handleDeleteChat(chatId) {
    if (!apiOnline || deletingChatId) return

    const chat = chats.find((item) => item.id === chatId)
    const label = chat?.title || 'este chat'
    const confirmed = window.confirm(`Apagar \"${label}\"?`)
    if (!confirmed) return

    setDeletingChatId(chatId)
    setError('')

    try {
      await fetchJSON(`/sessions/${chatId}`, { method: 'DELETE' })
      const remainingChats = chats.filter((item) => item.id !== chatId)
      setChats(remainingChats)

      if (activeChatId === chatId) {
        const nextChatId = remainingChats[0]?.id || null
        setSelectedResponseId(null)
        if (nextChatId) {
          await loadChat(nextChatId)
        } else {
          setActiveChatId(null)
          setActiveChat(null)
        }
      }
    } catch (err) {
      setError(normalizeErrorMessage(err))
    } finally {
      setDeletingChatId(null)
    }
  }

  async function handleAsk(question) {
    const clean = (question || draft).trim()
    if (!clean) return
    if (sending || sendLockRef.current) return

    const signature = questionSignature(clean)
    const now = Date.now()
    if (
      signature &&
      signature === lastSubmissionRef.current.signature &&
      now - lastSubmissionRef.current.ts < 1400
    ) {
      return
    }

    if (!apiOnline) {
      setError(`A API FastAPI não está acessível em ${API_BASE_URL}. Arranca primeiro: uvicorn api:app --reload`)
      return
    }

    if (!bootstrap?.rag_backend_ready) {
      setError('A API está online, mas o backend RAG ainda está indisponível. Verifica o /health e o índice vetorial.')
      return
    }

    sendLockRef.current = true
    lastSubmissionRef.current = { signature, ts: now }

    let chatId = activeChatId
    if (!chatId) {
      const chat = await createChat()
      chatId = chat?.id || null
      if (!chatId) {
        sendLockRef.current = false
        return
      }
    }

    setSending(true)
    setSendingQuestion(clean)
    setError('')
    try {
      const data = await fetchJSON(`/sessions/${chatId}/ask`, {
        method: 'POST',
        body: JSON.stringify({
          query: clean,
          category,
          top_k: topK,
        }),
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
            <div className="empty-panel empty-panel-compact">{apiOnline ? 'Ainda não existem chats.' : 'Sem ligação à API. Os chats aparecem aqui quando o backend estiver online.'}</div>
          )}
        </div>
      </aside>

      <main className="main-column">
        <header className="hero panel">
          <div>
            <h1>RAG para análise de contratos e avisos públicos</h1>
            <p>
              Faz perguntas sobre prazo, valor base, entidade adjudicante, critérios, caução,
              CPV e outros elementos relevantes, com respostas ancoradas em fontes.
            </p>
          </div>
          <div className="hero-actions">
            <ThemeToggle
              theme={theme}
              onToggle={() => setTheme((current) => (current === 'dark' ? 'light' : 'dark'))}
            />
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
              {bootstrap?.rag_backend_error ? trimText(bootstrap.rag_backend_error, 220) : 'Verifica o índice vetorial e as dependências do backend.'}
            </div>
            <button className="button" onClick={boot}>Atualizar estado</button>
          </section>
        ) : null}

        <section className="toolbar panel toolbar-compact">
          <div className="toolbar-group">
            <label>
              Categoria
              <select value={category} onChange={(event) => setCategory(event.target.value)}>
                {categories.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Top K
              <input
                type="number"
                min="1"
                max="12"
                value={topK}
                onChange={(event) => setTopK(Number(event.target.value) || 4)}
              />
            </label>
          </div>
          <div className="status-strip">
            <span className={classNames('status-pill', apiOnline ? 'status-ok' : 'status-warn')}>
              API: {apiOnline ? 'online' : 'offline'}
            </span>
            <span className={classNames('status-pill', bootstrap?.rag_backend_ready ? 'status-ok' : 'status-warn')}>
              Backend RAG: {bootstrap?.rag_backend_ready ? 'pronto' : 'indisponível'}
            </span>
            {selectedPayload?.confidence ? <ConfidenceBadge confidence={selectedPayload.confidence} /> : null}
          </div>
        </section>

        <section className={classNames('suggestions panel', hasDenseHistory && 'suggestions-compact')}>
          <div className="panel-header panel-header-compact">
            <h3>Perguntas sugeridas</h3>
            <div className="panel-header-actions">
              <span>{hasDenseHistory ? 'Sugestões rápidas' : 'Pontos de partida'}</span>
              {suggestionQuestions.length > compactSuggestionLimit ? (
                <button
                  type="button"
                  className="text-button"
                  onClick={() => setShowAllSuggestions((current) => !current)}
                >
                  {showAllSuggestions ? 'Ver menos' : 'Ver mais'}
                </button>
              ) : null}
            </div>
          </div>
          {visibleSuggestionQuestions.length ? (
            <div className="chip-row">
              {visibleSuggestionQuestions.map((question) => (
                <button
                  key={question}
                  className="chip"
                  onClick={() => handleAsk(question)}
                  disabled={!apiOnline || !bootstrap?.rag_backend_ready || sending}
                >
                  {question}
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-panel empty-panel-compact">Não há novas perguntas sugeridas.</div>
          )}
        </section>

        <section className="chat panel chat-panel">
          <div className="panel-header chat-panel-header">
            <h3>Chat</h3>
            <span>{activeChat?.messages?.length ? `${activeChat.messages.length} ${activeChat.messages.length === 1 ? 'mensagem' : 'mensagens'}` : 'Sem mensagens'}</span>
          </div>

          {loading ? <div className="empty-panel">A carregar aplicação…</div> : null}
          {error ? <div className="error-banner">{error}</div> : null}

          <div ref={messageListRef} className={classNames('message-list', 'message-list-expanded', sending && 'message-list-sending')} aria-live={sending ? 'polite' : 'off'}>
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
                    onClick={payload ? () => {
                      setSelectedResponseId(payload.id)
                      setSelectedInspectorTab('fontes')
                    } : undefined}
                  >
                    <div className="message-shell">
                      <div className={classNames('message-avatar', isAssistant ? 'message-avatar-assistant' : 'message-avatar-user')}>
                        {isAssistant ? '🤖' : 'Tu'}
                      </div>
                      <div className="message-body">
                        <div className="message-header-row">
                          <div className="message-role">{isAssistant ? 'Assistente' : 'Pergunta'}</div>
                          <div className="message-actions">
                            {payload ? <span className="message-tag">Selecionada</span> : null}
                            {payload ? (
                              <button
                                type="button"
                                className="message-copy-button"
                                onClick={(event) => {
                                  event.stopPropagation()
                                  handleCopyAnswer(payload.id, payload.answer?.markdown || message.content || '')
                                }}
                                title="Copiar resposta"
                              >
                                {copiedAnswerId === payload.id ? 'Copiado' : 'Copiar'}
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
                {apiOnline
                  ? 'Envia uma pergunta para começar.'
                  : 'Liga a API para criar chats e responder.'}
              </div>
            )}

            {sending && sendingQuestion ? (
              <article className="message-card message-assistant message-pending" role="status" aria-live="polite">
                <div className="message-shell">
                  <div className="message-avatar message-avatar-assistant">🤖</div>
                  <div className="message-body">
                    <div className="message-header-row">
                      <div className="message-role">Assistente</div>
                      <div className="message-actions">
                        <span className="message-tag message-tag-live">A responder…</span>
                      </div>
                    </div>
                    <div className="message-content pending-copy">
                      A analisar a tua pergunta: <strong>{sendingQuestion}</strong>
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

          <div className="composer-shell">
            <form className={classNames('composer', sending && 'composer-sending')} onSubmit={handleSubmit}>
              <textarea
                ref={composerRef}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    handleAsk()
                  }
                }}
                placeholder={sending ? 'A aguardar resposta do backend…' : 'Ex.: Qual é o prazo para apresentação das propostas?'}
                rows={3}
                disabled={sending}
              />
              <div className="composer-actions">
                <div className="composer-feedback">
                  <span className={classNames('composer-status-badge', sending && 'composer-status-badge-live')}>
                    {sending
                      ? 'A responder…'
                      : !apiOnline
                        ? 'API offline'
                        : !bootstrap?.rag_backend_ready
                          ? 'Backend indisponível'
                          : 'Pronto para perguntar'}
                  </span>
                  <span className="composer-hint">
                    {!apiOnline
                      ? 'Sem ligação à API.'
                      : !bootstrap?.rag_backend_ready
                        ? 'API online, mas backend RAG indisponível.'
                        : sending
                          ? 'A aguardar resposta do backend. Evitámos submissões duplicadas durante este pedido.'
                          : 'Enter envia • Shift+Enter cria nova linha.'}
                  </span>
                </div>
                <button className="button button-primary" type="submit" disabled={askDisabled}>
                  {sending ? 'A responder…' : !apiOnline ? 'API offline' : !bootstrap?.rag_backend_ready ? 'Backend indisponível' : 'Perguntar'}
                </button>
              </div>
            </form>
          </div>
        </section>
      </main>

      <aside className="inspector-column">
        <section className="panel inspector-panel">
          <div className="panel-header">
            <h3>Respostas</h3>
            <span>{responsesCountLabel}</span>
          </div>
          <ResponsePicker
            payloads={[...assistantPayloads].reverse()}
            selectedId={selectedResponseId}
            onSelect={(payloadId) => {
              setSelectedResponseId(payloadId)
              setSelectedInspectorTab('fontes')
            }}
          />
        </section>

        <InspectorTabs
          selectedPayload={selectedPayload}
          selectedTab={selectedInspectorTab}
          onChangeTab={setSelectedInspectorTab}
        />
      </aside>
    </div>
  )
}

export default App
