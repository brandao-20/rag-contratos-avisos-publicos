import React from 'react'
import { classNames, trimText } from '../utils/format'

function FavoriteItem({ item, onOpen, onRemove }) {
  return (
    <div className="favorite-item">
      <button type="button" className="favorite-open-button" onClick={() => onOpen(item)}>
        <strong>{item.chatTitle || 'Resposta guardada'}</strong>
        <span>{item.preview}</span>
      </button>
      <button type="button" className="icon-button small-icon-button" onClick={() => onRemove(item)} title="Remover favorito">×</button>
    </div>
  )
}

function ChatItem({ chat, active, deleting, onSelect, onDelete }) {
  return (
    <div className={classNames('chat-item-shell', active && 'chat-item-shell-active')}>
      <button className={classNames('chat-item chat-item-compact', active && 'chat-item-active')} onClick={() => onSelect(chat.id)} title={chat.title || 'Novo chat'}>
        <div className="chat-item-title">{chat.title || 'Novo chat'}</div>
      </button>
      <button
        type="button"
        className="chat-delete-hitbox"
        onClick={(event) => { event.stopPropagation(); onDelete(chat.id) }}
        disabled={deleting}
        title="Apagar chat"
      >
        ×
      </button>
    </div>
  )
}

export default function Sidebar({
  chats,
  activeChatId,
  onSelectChat,
  onCreateChat,
  onDeleteChat,
  deletingChatId,
  searchValue,
  onSearchValue,
  favorites,
  onOpenFavorite,
  onRemoveFavorite,
}) {
  const filteredChats = chats.filter((chat) => {
    const needle = searchValue.trim().toLowerCase()
    if (!needle) return true
    const haystack = `${chat.title || ''} ${chat.last_message_preview || ''}`.toLowerCase()
    return haystack.includes(needle)
  })

  return (
    <aside className="sidebar panel sticky-panel">
      <div className="sidebar-top">
        <div>
          <h2>Chats</h2>
          <div className="sidebar-subtitle">{filteredChats.length} visíveis</div>
        </div>
        <button className="button button-primary button-small" type="button" onClick={onCreateChat}>+ Novo</button>
      </div>

      <input
        value={searchValue}
        onChange={(event) => onSearchValue(event.target.value)}
        placeholder="Pesquisar chats…"
        className="sidebar-search"
      />

      {favorites.length ? (
        <section className="sidebar-section">
          <div className="sidebar-section-header">
            <div className="eyebrow">Guardados</div>
            <span>{favorites.length}</span>
          </div>
          <div className="favorite-list">
            {favorites.slice(0, 6).map((item) => (
              <FavoriteItem key={item.key} item={item} onOpen={onOpenFavorite} onRemove={onRemoveFavorite} />
            ))}
          </div>
        </section>
      ) : null}

      <section className="sidebar-section sidebar-section-grow">
        <div className="sidebar-section-header">
          <div className="eyebrow">Chats</div>
          <span>{chats.length}</span>
        </div>
        <div className="chat-list">
          {filteredChats.length ? (
            filteredChats.map((chat) => (
              <ChatItem
                key={chat.id}
                chat={chat}
                active={chat.id === activeChatId}
                deleting={deletingChatId === chat.id}
                onSelect={onSelectChat}
                onDelete={onDeleteChat}
              />
            ))
          ) : (
            <div className="empty-panel empty-panel-compact">
              {searchValue.trim() ? `Sem resultados para “${trimText(searchValue, 24)}”.` : 'Ainda não existem chats.'}
            </div>
          )}
        </div>
      </section>
    </aside>
  )
}
