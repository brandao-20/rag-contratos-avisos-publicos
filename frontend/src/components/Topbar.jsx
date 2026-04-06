import React from 'react'
import { classNames } from '../utils/format'
import { MODE_OPTIONS } from '../constants'

export default function Topbar({
  mode,
  onChangeMode,
  theme,
  onToggleTheme,
  onRefresh,
  canExport,
  onExportJson,
  onExportMarkdown,
}) {
  return (
    <header className="topbar panel">
      <div className="topbar-branding">
        <div className="brand-mark" aria-hidden="true">◈</div>
        <div>
          <div className="eyebrow">Análise documental</div>
          <div className="brand-title">Procedimentos públicos</div>
        </div>
      </div>

      <div className="topbar-center">
        <div className="mode-switcher" role="tablist" aria-label="Modos da aplicação">
          {MODE_OPTIONS.map((item) => (
            <button
              key={item.id}
              className={classNames('mode-chip', mode === item.id && 'mode-chip-active')}
              onClick={() => onChangeMode(item.id)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="topbar-actions">
        <button className="icon-button" type="button" onClick={onToggleTheme} title="Alternar tema">
          {theme === 'dark' ? '☀' : '☾'}
        </button>
        <button className="icon-button" type="button" onClick={onRefresh} title="Atualizar estado">
          ↻
        </button>
        {canExport ? (
          <div className="export-group">
            <button className="icon-button" type="button" onClick={onExportMarkdown} title="Exportar chat em Markdown">
              ⤓
            </button>
            <button className="icon-button" type="button" onClick={onExportJson} title="Exportar chat em JSON">
              {'{}'}
            </button>
          </div>
        ) : null}
      </div>
    </header>
  )
}
