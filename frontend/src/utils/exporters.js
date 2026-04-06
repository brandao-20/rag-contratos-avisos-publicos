export function downloadTextFile(filename, content, mime = 'text/plain;charset=utf-8') {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export function exportChatAsJson(chat) {
  const filename = `chat-${chat?.id || 'sessao'}.json`
  downloadTextFile(filename, JSON.stringify(chat, null, 2), 'application/json;charset=utf-8')
}

export function exportChatAsMarkdown(chat) {
  const title = chat?.title || 'Chat sem título'
  const lines = [`# ${title}`, '']
  ;(chat?.messages || []).forEach((message) => {
    const role = message?.role === 'assistant' ? 'Assistente' : 'Utilizador'
    lines.push(`## ${role}`)
    lines.push(message?.content || '')
    lines.push('')
  })
  const filename = `chat-${chat?.id || 'sessao'}.md`
  downloadTextFile(filename, lines.join('\n'), 'text/markdown;charset=utf-8')
}
