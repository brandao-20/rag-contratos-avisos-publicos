import React from 'react'

export default function Composer({
  draft,
  onChangeDraft,
  onSubmit,
  onKeyDown,
  disabled,
  sending,
  composerRef,
  apiOnline,
  ragReady,
}) {
  return (
    <form className="composer-shell" onSubmit={onSubmit}>
      <div className={`composer ${sending ? 'composer-sending' : ''}`}>
        <textarea
          ref={composerRef}
          value={draft}
          onChange={(event) => onChangeDraft(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Faz uma pergunta sobre contratos ou avisos públicos…"
          disabled={disabled}
        />
        <div className="composer-footer">
          <div className="composer-hint">
            {sending
              ? 'A responder…'
              : !apiOnline
                ? 'API offline.'
                : !ragReady
                  ? 'Backend RAG indisponível.'
                  : 'Enter envia · Shift+Enter nova linha'}
          </div>
          <button className="button button-primary" type="submit" disabled={disabled || !draft.trim()}>
            {sending ? 'A responder…' : 'Perguntar'}
          </button>
        </div>
      </div>
    </form>
  )
}
