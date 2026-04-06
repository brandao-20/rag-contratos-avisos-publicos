import { API_BASE_URL } from '../constants'

export async function fetchJSON(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })

  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const body = await response.json()
      detail = body?.detail || body?.message || detail
    } catch (_) {}
    const error = new Error(String(detail))
    error.status = response.status
    error.detail = String(detail)
    throw error
  }

  return response.json()
}
