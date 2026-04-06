const STOPWORDS = new Set([
  'a','as','o','os','de','do','da','dos','das','e','ou','para','por','com','sem','em','no','na','nos','nas',
  'um','uma','uns','umas','qual','quais','que','é','sao','são','ha','há','existe','existem','ser','foi','referido',
  'referidos','referida','referidas','indicado','indicados','indicada','indicadas',
])

const TOKEN_REPLACEMENTS = {
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

export function normalizeQuestionKey(value) {
  return String(value || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[?!.:,;()\[\]{}]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function questionSignature(value) {
  const normalized = normalizeQuestionKey(value)
  if (!normalized) return ''
  const tokens = normalized
    .split(' ')
    .map((token) => TOKEN_REPLACEMENTS[token] || token)
    .map((token) => (token.length > 4 && token.endsWith('s') ? token.slice(0, -1) : token))
    .filter((token) => token && !STOPWORDS.has(token) && token.length > 2)
  return tokens.sort().join(' ')
}

export function filterPendingSuggestedQuestions(suggestions, askedQuestions) {
  if (!suggestions?.length) return []
  const asked = new Set((askedQuestions || []).map(questionSignature).filter(Boolean))
  return suggestions.filter((question) => {
    const signature = questionSignature(question)
    return signature && !asked.has(signature)
  })
}
