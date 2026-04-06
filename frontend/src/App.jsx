import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchJSON } from './api/client'
import { FALLBACK_BOOTSTRAP, FALLBACK_CATEGORIES, FALLBACK_SUGGESTIONS } from './constants'
import { usePersistentState } from './hooks/usePersistentState'
import { getAssistantPayloads, normalizeErrorMessage, trimText } from './utils/format'
import { exportChatAsJson, exportChatAsMarkdown } from './utils/exporters'
import { filterPendingSuggestedQuestions } from './utils/questions'
import Topbar from './components/Topbar'
import Sidebar from './components/Sidebar'
import HeroHome from './components/HeroHome'
import Composer from './components/Composer'
import MessageCard from './components/MessageCard'
import InspectorPanel from './components/InspectorPanel'
import CorpusExplorer from './components/CorpusExplorer'
import GlossaryView from './components/GlossaryView'
import ConfirmDialog from './components/ConfirmDialog'
import ToastStack from './components/ToastStack'

const SEARCH_PREFIXES = [
  'procura ',
  'mostra ',
  'encontra ',
  'indica um procedimento',
  'dá-me um procedimento',
  'da-me um procedimento',
  'lista ',
  'que contratos ativos',
  'quais contratos ativos',
  'que contratos existem',
  'quais contratos existem',
  'que avisos existem',
  'quais avisos existem',
  'todos os contratos',
  'todos os avisos',
]

const CONTEXT_PREFIXES = [
  'qual ',
  'quais ',
  'quem ',
  'onde ',
  'quando ',
  'existe ',
  'há ',
  'ha ',
  'tem ',
  'indica ',
  'neste ',
  'deste ',
  'este procedimento',
  'este contrato',
  'este aviso',
]

function App() {
  const [bootstrap, setBootstrap] = useState(FALLBACK_BOOTSTRAP)
  const [apiOnline, setApiOnline] = useState(false)
  const [corpusSections, setCorpusSections] = useState([])
  const [glossaryEntries, setGlossaryEntries] = useState([])
  const [chats, setChats] = useState([])
  const [activeChatId, setActiveChatId] = useState(null)
  const [activeChat, setActiveChat] = useState(null)
  const [selectedResponseId, setSelectedResponseId] = useState(null)
  const [selectedInspectorTab, setSelectedInspectorTab] = useState('fontes')
  const [selectedCitation, setSelectedCitation] = useState(null)
  const [draft, setDraft] = useState('')
  const [category, setCategory] = useState('todos')
  const [topK, setTopK] = useState(4)
  const [mode, setMode] = usePersistentState('rag-public-mode', 'chat')
  const [theme, setTheme] = usePersistentState('rag-theme', 'light')
  const [favorites, setFavorites] = usePersistentState('rag-favorite-responses', [])
  const [sidebarSearch, setSidebarSearch] = useState('')
  const [glossarySearch, setGlossarySearch] = useState('')
  const [glossaryCategory, setGlossaryCategory] = useState('todos')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [sendingQuestion, setSendingQuestion] = useState('')
  const [deletingChatId, setDeletingChatId] = useState(null)
  const [copiedAnswerId, setCopiedAnswerId] = useState(null)
  const [error, setError] = useState('')
  const [pendingContextSourceId, setPendingContextSourceId] = useState(null)
  const [confirmState, setConfirmState] = useState(null)
  const [toasts, setToasts] = useState([])

  const composerRef = useRef(null)
  const messageListRef = useRef(null)
  const previousChatRef = useRef(null)
  const previousCountRef = useRef(0)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  const pushToast = useCallback((type, title, message = '') => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    setToasts((current) => [...current, { id, type, title, message }])
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id))
    }, 3400)
  }, [])

  const dismissToast = useCallback((toastId) => {
    setToasts((current) => current.filter((toast) => toast.id !== toastId))
  }, [])

  const loadChats = useCallback(async (preferredId = null) => {
    const summaries = await fetchJSON('/sessions')
    setChats(summaries)
    const nextId = preferredId || activeChatId || summaries[0]?.id || null
    if (!nextId) {
      setActiveChatId(null)
      setActiveChat(null)
      setSelectedResponseId(null)
      setSelectedCitation(null)
      return
    }
    try {
      const detail = await fetchJSON(`/sessions/${nextId}`)
      setActiveChatId(detail.id)
      setActiveChat(detail)
    } catch (_) {
      setActiveChatId(null)
      setActiveChat(null)
      setSelectedResponseId(null)
      setSelectedCitation(null)
    }
  }, [activeChatId])

  const boot = useCallback(async () => {
    setLoading(true)
    try {
      const [health, bootstrapPayload, corpusPayload, glossaryPayload] = await Promise.all([
        fetchJSON('/health'),
        fetchJSON('/bootstrap'),
        fetchJSON('/corpus/overview').catch(() => []),
        fetchJSON('/glossary').catch(() => []),
      ])
      setApiOnline(health?.status === 'ok')
      setBootstrap(bootstrapPayload || FALLBACK_BOOTSTRAP)
      setCategory((current) => bootstrapPayload?.default_category || current || 'todos')
      setCorpusSections(Array.isArray(corpusPayload) ? corpusPayload : [])
      setGlossaryEntries(Array.isArray(glossaryPayload) ? glossaryPayload : [])
      await loadChats()
      setError('')
    } catch (err) {
      setApiOnline(false)
      setBootstrap(FALLBACK_BOOTSTRAP)
      setCorpusSections([])
      setGlossaryEntries([])
      setError(normalizeErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [loadChats])

  useEffect(() => {
    boot()
  }, [boot])

  const assistantPayloads = useMemo(() => getAssistantPayloads(activeChat), [activeChat])
  const latestPayload = assistantPayloads[assistantPayloads.length - 1] || null
  const selectedPayload = useMemo(() => {
    if (!assistantPayloads.length) return null
    return assistantPayloads.find((item) => item.id === selectedResponseId) || latestPayload
  }, [assistantPayloads, selectedResponseId, latestPayload])

  const inferAutomaticSourceId = useCallback((question) => {
    const normalized = String(question || '').trim().toLowerCase()
    if (!normalized) return null
    const sourceId = pendingContextSourceId
      || selectedPayload?.sources?.[0]?.source_id
      || latestPayload?.sources?.[0]?.source_id
      || null
    if (!sourceId) return null
    if (SEARCH_PREFIXES.some((prefix) => normalized.startsWith(prefix))) return null
    if (normalized.includes('outro procedimento') || normalized.includes('outra fonte') || normalized.includes('noutro')) return null
    if (normalized.includes('neste ') || normalized.includes('deste ')) return sourceId
    if (CONTEXT_PREFIXES.some((prefix) => normalized.startsWith(prefix))) return sourceId
    if (normalized.split(' ').length <= 7) return sourceId
    return null
  }, [latestPayload, pendingContextSourceId, selectedPayload])

  useEffect(() => {
    if (assistantPayloads.length && !selectedResponseId) {
      setSelectedResponseId(assistantPayloads[assistantPayloads.length - 1].id)
    }
  }, [assistantPayloads, selectedResponseId])

  const askedQuestions = useMemo(
    () => (activeChat?.messages || []).filter((item) => item?.role === 'user').map((item) => item.content),
    [activeChat],
  )

  const baseSuggestions = bootstrap?.question_suggestions?.length ? bootstrap.question_suggestions : FALLBACK_SUGGESTIONS
  const pendingSuggestions = useMemo(
    () => filterPendingSuggestedQuestions(baseSuggestions, askedQuestions),
    [baseSuggestions, askedQuestions],
  )
  const visibleSuggestions = pendingSuggestions.slice(0, 6)
  const categories = bootstrap?.categories || FALLBACK_CATEGORIES
  const ragReady = !!bootstrap?.rag_backend_ready
  const ragMode = bootstrap?.rag_backend_mode || 'offline'
  const ragMessage = bootstrap?.rag_backend_message || ''
  const canAsk = apiOnline && ragReady && !sending

  useEffect(() => {
    const textarea = composerRef.current
    if (!textarea) return
    textarea.style.height = '0px'
    const nextHeight = Math.min(Math.max(textarea.scrollHeight, 112), 240)
    textarea.style.height = `${nextHeight}px`
  }, [draft])

  useEffect(() => {
    const container = messageListRef.current
    const count = activeChat?.messages?.length || 0
    if (!container) {
      previousChatRef.current = activeChatId
      previousCountRef.current = count
      return
    }
    const chatChanged = previousChatRef.current !== activeChatId
    const countIncreased = count > previousCountRef.current
    if (chatChanged || countIncreased || sending) {
      window.requestAnimationFrame(() => {
        container.scrollTo({ top: container.scrollHeight, behavior: chatChanged ? 'auto' : 'smooth' })
      })
    }
    previousChatRef.current = activeChatId
    previousCountRef.current = count
  }, [activeChatId, activeChat?.messages?.length, sending])

  const createChat = useCallback(async () => {
    if (!apiOnline) {
      const message = 'API FastAPI não acessível. Arranca primeiro: uvicorn api:app --reload'
      setError(message)
      pushToast('error', 'API offline', message)
      return null
    }
    try {
      const detail = await fetchJSON('/sessions', { method: 'POST', body: JSON.stringify({ title: 'Novo chat' }) })
      setActiveChatId(detail.id)
      setActiveChat(detail)
      setSelectedResponseId(null)
      setSelectedCitation(null)
      await loadChats(detail.id)
      pushToast('success', 'Chat criado', 'Já podes começar uma nova análise documental.')
      return detail
    } catch (err) {
      const message = normalizeErrorMessage(err)
      setError(message)
      pushToast('error', 'Falha ao criar chat', message)
      return null
    }
  }, [apiOnline, loadChats, pushToast])

  const loadChat = useCallback(async (chatId) => {
    try {
      const detail = await fetchJSON(`/sessions/${chatId}`)
      setActiveChatId(detail.id)
      setActiveChat(detail)
      setSelectedResponseId(null)
      setSelectedCitation(null)
      setMode('chat')
    } catch (err) {
      const message = normalizeErrorMessage(err)
      setError(message)
      pushToast('error', 'Chat indisponível', message)
      await loadChats()
    }
  }, [loadChats, pushToast, setMode])

  const requestDeleteChat = useCallback((chatId) => {
    const chat = chats.find((item) => item.id === chatId)
    const label = chat?.title || 'este chat'
    setConfirmState({
      tone: 'danger',
      title: 'Apagar chat?',
      message: `Vais remover “${label}”. Esta ação elimina a conversa atual e não pode ser revertida.`,
      confirmLabel: 'Apagar',
      cancelLabel: 'Cancelar',
      onConfirm: async () => {
        if (deletingChatId) return
        setDeletingChatId(chatId)
        try {
          await fetchJSON(`/sessions/${chatId}`, { method: 'DELETE' })
          const remaining = chats.filter((item) => item.id !== chatId)
          setChats(remaining)
          if (activeChatId === chatId) {
            const nextId = remaining[0]?.id || null
            if (nextId) await loadChat(nextId)
            else {
              setActiveChatId(null)
              setActiveChat(null)
              setSelectedResponseId(null)
              setSelectedCitation(null)
            }
          }
          pushToast('success', 'Chat apagado', 'A conversa foi removida com sucesso.')
        } catch (err) {
          const message = normalizeErrorMessage(err)
          setError(message)
          pushToast('error', 'Falha ao apagar chat', message)
        } finally {
          setDeletingChatId(null)
          setConfirmState(null)
        }
      },
      onCancel: () => setConfirmState(null),
    })
  }, [activeChatId, chats, deletingChatId, loadChat, pushToast])

  const handleAsk = useCallback(async (questionOverride = null) => {
    const clean = String(questionOverride || draft).replace(/\s+/g, ' ').trim()
    if (!clean) return
    if (!apiOnline) {
      const message = 'API FastAPI não acessível. Arranca primeiro: uvicorn api:app --reload'
      setError(message)
      pushToast('error', 'API offline', message)
      return
    }
    if (!ragReady) {
      const message = 'A aplicação está online, mas o motor documental ainda não ficou utilizável. Confirma o corpus local e o estado do backend.'
      setError(message)
      pushToast('error', 'Backend documental indisponível', message)
      return
    }

    let targetChatId = activeChatId
    if (!targetChatId) {
      const chat = await createChat()
      targetChatId = chat?.id || null
      if (!targetChatId) return
    }

    setSending(true)
    setSendingQuestion(clean)
    setError('')
    try {
      const preferredSourceId = inferAutomaticSourceId(clean)
      const response = await fetchJSON(`/sessions/${targetChatId}/ask`, {
        method: 'POST',
        body: JSON.stringify({ query: clean, category, top_k: topK, preferred_source_id: preferredSourceId || undefined }),
      })
      setActiveChat(response.session)
      setActiveChatId(response.session.id)
      setSelectedResponseId(null)
      setSelectedCitation(null)
      setDraft('')
      setPendingContextSourceId(null)
      await loadChats(response.session.id)
      setMode('chat')
    } catch (err) {
      const message = normalizeErrorMessage(err)
      setError(message)
      pushToast('error', 'Falha ao responder', message)
      await boot()
    } finally {
      setPendingContextSourceId(null)
      setSending(false)
      setSendingQuestion('')
    }
  }, [activeChatId, apiOnline, boot, category, createChat, draft, inferAutomaticSourceId, loadChats, pushToast, ragReady, setMode, topK])

  const handleSubmit = useCallback((event) => {
    event.preventDefault()
    handleAsk()
  }, [handleAsk])

  const handleComposerKeyDown = useCallback((event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleAsk()
    }
  }, [handleAsk])

  const handleUseFollowUp = useCallback((question, payload) => {
    setDraft(question)
    setPendingContextSourceId(payload?.sources?.[0]?.source_id || null)
    window.requestAnimationFrame(() => {
      const composer = composerRef.current
      if (composer) {
        composer.focus()
        composer.setSelectionRange(question.length, question.length)
      }
    })
  }, [])

  const handleCopyAnswer = useCallback(async (payload) => {
    try {
      await navigator.clipboard.writeText(payload?.answer?.markdown || payload?.content || '')
      setCopiedAnswerId(payload.id)
      pushToast('success', 'Resposta copiada', 'O conteúdo foi copiado para a área de transferência.')
      window.setTimeout(() => setCopiedAnswerId((current) => (current === payload.id ? null : current)), 1400)
    } catch (_) {
      pushToast('error', 'Não foi possível copiar', 'O browser não permitiu copiar a resposta.')
    }
  }, [pushToast])

  const toggleFavorite = useCallback((payload) => {
    if (!activeChat) return
    let added = false
    setFavorites((current) => {
      const exists = current.some((item) => item.key === payload.key)
      if (exists) return current.filter((item) => item.key !== payload.key)
      added = true
      const nextItem = {
        key: payload.key,
        responseId: payload.id,
        sessionId: activeChat.id,
        chatTitle: activeChat.title,
        preview: payload.preview,
      }
      return [nextItem, ...current].slice(0, 24)
    })
    pushToast(added ? 'success' : 'info', added ? 'Resposta guardada' : 'Guardado removido', added ? 'A resposta foi adicionada aos guardados.' : 'A resposta foi removida dos guardados.')
  }, [activeChat, pushToast, setFavorites])

  const openFavorite = useCallback(async (item) => {
    try {
      await loadChat(item.sessionId)
      setSelectedResponseId(item.responseId)
      setMode('chat')
    } catch (_) {
      setFavorites((current) => current.filter((favorite) => favorite.key !== item.key))
      pushToast('info', 'Guardado limpo', 'O chat original já não existia e o guardado foi removido automaticamente.')
    }
  }, [loadChat, pushToast, setFavorites, setMode])

  if (loading) {
    return <div className="loading-screen">A carregar a aplicação…</div>
  }

  return (
    <>
      <div className="app-shell">
        <Sidebar
          chats={chats}
          activeChatId={activeChatId}
          onSelectChat={loadChat}
          onCreateChat={createChat}
          onDeleteChat={requestDeleteChat}
          deletingChatId={deletingChatId}
          searchValue={sidebarSearch}
          onSearchValue={setSidebarSearch}
          favorites={favorites}
          onOpenFavorite={openFavorite}
          onRemoveFavorite={(item) => {
            setFavorites((current) => current.filter((favorite) => favorite.key !== item.key))
            pushToast('info', 'Guardado removido', 'O item foi removido da lista de guardados.')
          }}
        />

        <main className="workspace">
          <Topbar
            mode={mode}
            onChangeMode={setMode}
            apiOnline={apiOnline}
            ragReady={ragReady}
            ragMode={ragMode}
            theme={theme}
            onToggleTheme={() => setTheme((current) => (current === 'dark' ? 'light' : 'dark'))}
            onRefresh={boot}
            canExport={!!activeChat?.messages?.length}
            onExportJson={() => {
              exportChatAsJson(activeChat)
              pushToast('success', 'Chat exportado', 'Foi gerado um ficheiro JSON com a conversa atual.')
            }}
            onExportMarkdown={() => {
              exportChatAsMarkdown(activeChat)
              pushToast('success', 'Chat exportado', 'Foi gerado um ficheiro Markdown com a conversa atual.')
            }}
          />

          {error ? <section className="panel notice-banner notice-warning">{trimText(error, 340)}</section> : null}
          {!apiOnline ? <section className="panel notice-banner">API offline. Arranca primeiro: <code>uvicorn api:app --reload</code></section> : null}
          {apiOnline && ragReady && ragMode === 'lexical' ? (
            <section className="panel notice-banner notice-info">{ragMessage || 'Modo documental local ativo: as perguntas continuam disponíveis com recuperação lexical e respostas ancoradas nas fontes.'}</section>
          ) : null}
          {apiOnline && !ragReady ? <section className="panel notice-banner">API online, mas o backend documental ainda não está pronto. Verifica o corpus local, o índice e o Ollama se precisares do modo vetorial/LLM.</section> : null}

          {mode === 'chat' ? (
            <section className="panel chat-panel">
              {!activeChat?.messages?.length ? (
                <HeroHome suggestions={visibleSuggestions.slice(0, 6)} onAsk={handleAsk} disabled={!canAsk} />
              ) : null}

              {activeChat ? (
                <div className="chat-toolbar panel-toolbar">
                  <div>
                    <div className="eyebrow">Sessão ativa</div>
                    <h3>{activeChat.title || 'Novo chat'}</h3>
                  </div>
                  <div className="toolbar-controls">
                    <label>
                      Categoria
                      <select value={category} onChange={(event) => setCategory(event.target.value)}>
                        {categories.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
                      </select>
                    </label>
                    <label>
                      Top K
                      <input type="number" min="1" max="12" value={topK} onChange={(event) => setTopK(Number(event.target.value) || 4)} />
                    </label>
                  </div>
                </div>
              ) : null}

              {activeChat?.messages?.length ? (
                <div className="message-list" ref={messageListRef}>
                  {activeChat.messages.map((message, index) => {
                    const assistantIndex = getAssistantPayloads({ id: activeChat.id, messages: activeChat.messages.slice(0, index + 1) }).slice(-1)[0]
                    const payload = message.role === 'assistant'
                      ? assistantPayloads.find((item) => item.id === assistantIndex?.id)
                      : null
                    const filteredFollowUps = payload ? filterPendingSuggestedQuestions(payload.followUps || [], askedQuestions).slice(0, 3) : []

                    return (
                      <MessageCard
                        key={`${message.role}-${index}`}
                        message={message}
                        payload={payload ? { ...payload, followUps: filteredFollowUps } : null}
                        selected={payload?.id === selectedPayload?.id}
                        onSelect={() => {
                          if (!payload) return
                          setSelectedResponseId(payload.id)
                          setSelectedInspectorTab('fontes')
                        }}
                        onCopy={() => payload && handleCopyAnswer(payload)}
                        copied={payload?.id === copiedAnswerId}
                        onFavorite={() => payload && toggleFavorite(payload)}
                        favorite={payload ? favorites.some((item) => item.key === payload.key) : false}
                        onUseFollowUp={(question) => handleUseFollowUp(question, payload)}
                        showFollowUps={payload?.id === latestPayload?.id && filteredFollowUps.length > 0}
                      />
                    )
                  })}

                  {sending ? (
                    <article className="message-card message-assistant message-pending">
                      <div className="message-shell">
                        <div className="message-avatar message-avatar-assistant">IA</div>
                        <div className="message-body">
                          <div className="message-role">Assistente</div>
                          <div className="pending-copy">A responder à pergunta: <strong>{sendingQuestion}</strong></div>
                          <div className="pending-loader"><span /><span /><span /></div>
                        </div>
                      </div>
                    </article>
                  ) : null}
                </div>
              ) : (
                <div className="empty-panel chat-empty-panel">Cria um chat ou usa uma pergunta sugerida para começar.</div>
              )}

              <Composer
                draft={draft}
                onChangeDraft={setDraft}
                onSubmit={handleSubmit}
                onKeyDown={handleComposerKeyDown}
                disabled={!apiOnline || sending}
                sending={sending}
                composerRef={composerRef}
                apiOnline={apiOnline}
                ragReady={ragReady}
              />
            </section>
          ) : null}

          {mode === 'corpus' ? <CorpusExplorer sections={corpusSections} onAsk={handleAsk} /> : null}
          {mode === 'glossary' ? (
            <GlossaryView
              entries={glossaryEntries}
              search={glossarySearch}
              onSearch={setGlossarySearch}
              category={glossaryCategory}
              onCategory={setGlossaryCategory}
            />
          ) : null}
        </main>

        <InspectorPanel
          selectedPayload={selectedPayload}
          selectedTab={selectedInspectorTab}
          onChangeTab={setSelectedInspectorTab}
          selectedCitation={selectedCitation}
          onSelectCitation={setSelectedCitation}
          debugMode={false}
        />
      </div>

      <ConfirmDialog
        open={!!confirmState}
        tone={confirmState?.tone || 'danger'}
        title={confirmState?.title || ''}
        message={confirmState?.message || ''}
        confirmLabel={confirmState?.confirmLabel || 'Confirmar'}
        cancelLabel={confirmState?.cancelLabel || 'Cancelar'}
        onConfirm={confirmState?.onConfirm || (() => {})}
        onCancel={confirmState?.onCancel || (() => setConfirmState(null))}
      />
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </>
  )
}

export default App
