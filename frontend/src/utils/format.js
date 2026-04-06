export function classNames(...items) {
  return items.filter(Boolean).join(' ')
}

export function stripMarkdownForPreview(value) {
  return String(value || '')
    .replace(/^##\s+/gm, '')
    .replace(/\[(\d+)\]/g, '')
    .replace(/\*\*/g, '')
    .replace(/`/g, '')
    .replace(/^[\-*•]\s+/gm, '')
    .replace(/^\d+\.\s+/gm, '')
    .replace(/\n+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function trimText(value, maxLength = 140) {
  const text = stripMarkdownForPreview(value)
  if (!text) return 'Sem conteúdo.'
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text
}

export function formatDateTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('pt-PT', { dateStyle: 'short', timeStyle: 'short' }).format(date)
}

export function formatCitationCountLabel(count) {
  const safeCount = Number(count || 0)
  return `${safeCount} ${safeCount === 1 ? 'citação' : 'citações'}`
}

export function sameNormalizedLabel(a, b) {
  return String(a || '').trim().toLowerCase() === String(b || '').trim().toLowerCase()
}

export function normalizeErrorMessage(err) {
  const raw = typeof err === 'string' ? err : err?.detail || err?.message || 'Erro desconhecido.'
  const text = String(raw || '').trim()
  const normalized = text.toLowerCase()

  if (normalized.includes('localhost') && normalized.includes('11434')) {
    return 'O Ollama não está acessível neste momento. O sistema pode continuar em modo documental local, mas a síntese por LLM e alguns embeddings vetoriais deixam de estar disponíveis enquanto o serviço não arrancar.'
  }
  if (normalized.includes('índice vetorial inexistente')) {
    return 'Ainda não existe índice vetorial. Corre primeiro a ingestão ou usa o fallback documental se o corpus local estiver disponível.'
  }
  if (normalized.includes('sem índice vetorial utilizável')) {
    return 'Nem o índice vetorial nem o fallback documental local estão prontos. Confirma a pasta data/raw_docs e volta a correr a ingestão.'
  }
  if (normalized.includes('backend rag indisponível')) {
    return 'O backend respondeu, mas não conseguiu processar a pergunta com o motor RAG atual. Confirma o Ollama, o índice e o estado do corpus.'
  }
  return text
}

export function renderStructuredValue(key, value) {
  if (key === 'referencias_relevantes' && Array.isArray(value)) {
    return value.map((item, index) => ({
      id: `${item?.citation || index}`,
      citation: item?.citation || `[${index + 1}]`,
      summary: item?.summary || String(item),
    }))
  }
  if (Array.isArray(value)) return value.join(', ')
  return String(value)
}

export function buildAssistantPayload(message, index, sessionId) {
  const qa = message?.qa_result || {}
  const answerMarkdown = qa.answer?.markdown || message?.content || ''
  return {
    id: `msg-${index}`,
    key: `${sessionId || 'chat'}:msg-${index}`,
    preview: trimText(answerMarkdown, 110),
    content: message?.content || '',
    createdAt: message?.created_at || null,
    answer: qa.answer || null,
    confidence: qa.confidence || null,
    sources: qa.sources || qa.sources_grouped || [],
    structuredData: qa.structured_data || {},
    followUps: qa.follow_up_questions || [],
    proceduralSteps: qa.procedural_steps || [],
  }
}

export function getAssistantPayloads(chat) {
  if (!chat?.messages?.length) return []
  return chat.messages
    .map((message, index) => (message?.role === 'assistant' ? buildAssistantPayload(message, index, chat.id) : null))
    .filter(Boolean)
}
