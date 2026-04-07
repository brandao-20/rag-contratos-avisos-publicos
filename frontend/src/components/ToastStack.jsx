import React from 'react'
import { classNames } from '../utils/format'

export default function ToastStack({ toasts, onDismiss }) {
  if (!toasts?.length) return null

  return (
    <div className="toast-stack" aria-live="polite" aria-atomic="false">
      {toasts.map((toast) => (
        <div key={toast.id} className={classNames('toast', `toast-${toast.type || 'info'}`)} role="status">
          <div className="toast-body">
            <div className="toast-title">{toast.title}</div>
            {toast.message ? <div className="toast-message">{toast.message}</div> : null}
          </div>
          <button
            type="button"
            className="toast-close"
            onClick={() => onDismiss(toast.id)}
            aria-label="Fechar notificação"
            title="Fechar notificação"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}
