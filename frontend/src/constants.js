const DEFAULT_API_BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL).replace(/\/$/, '')

export const FALLBACK_CATEGORIES = [
  { id: 'todos', label: 'Todos os documentos' },
  { id: 'contratacao_publica', label: 'Contratação pública' },
  { id: 'aviso_publico', label: 'Avisos públicos' },
  { id: 'documento_publico', label: 'Outros documentos públicos' },
]

export const FALLBACK_SUGGESTIONS = [
  'Mostra um procedimento e identifica o objeto.',
  'Mostra um procedimento com preço base explícito.',
  'Mostra um procedimento com prazo para apresentação das propostas.',
  'Mostra um procedimento onde exista prestação de caução.',
  'Mostra um procedimento e indica o CPV.',
  'Mostra um procedimento e identifica a entidade adjudicante.',
  'Mostra um procedimento com lotes.',
  'Mostra um procedimento e indica o local de execução.',
]

export const FALLBACK_BOOTSTRAP = {
  api_version: 'offline',
  product_title: 'RAG para análise de contratos e avisos públicos',
  question_suggestions: FALLBACK_SUGGESTIONS,
  categories: FALLBACK_CATEGORIES,
  default_category: 'todos',
  sessions_enabled: true,
  rag_backend_ready: false,
  rag_backend_error: null,
  rag_backend_mode: 'offline',
  rag_backend_message: null,
  recommended_frontend: 'react',
}

export const MODE_OPTIONS = [
  { id: 'chat', label: 'Conversar' },
  { id: 'corpus', label: 'Explorar corpus' },
  { id: 'glossary', label: 'Glossário' },
]

export const STRUCTURED_LABELS = {
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
