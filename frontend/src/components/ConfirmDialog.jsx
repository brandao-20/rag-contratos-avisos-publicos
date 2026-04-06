import React from 'react'
import { classNames } from '../utils/format'

export default function ConfirmDialog({ open, tone = 'danger', title, message, confirmLabel = 'Confirmar', cancelLabel = 'Cancelar', onConfirm, onCancel }) {
  if (!open) return null

  return (
    <div className="confirm-overlay" role="presentation" onClick={onCancel}>
      <div
        className={classNames('confirm-dialog', `confirm-${tone}`)}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="confirm-icon" aria-hidden="true">{tone === 'danger' ? '!' : '✓'}</div>
        <div className="confirm-content">
          <h3 id="confirm-dialog-title">{title}</h3>
          {message ? <p>{message}</p> : null}
        </div>
        <div className="confirm-actions">
          <button type="button" className="button button-secondary" onClick={onCancel}>{cancelLabel}</button>
          <button type="button" className={classNames('button', tone === 'danger' ? 'button-danger' : 'button-primary')} onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  )
}
