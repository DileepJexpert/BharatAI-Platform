const API_BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail || `API error: ${res.status}`)
  }
  return res.json()
}

export interface HealthResponse {
  status: string
  platform: string
  plugins: string[]
  version?: string
}

export interface ModelInfo {
  current_model: string
  available_models?: string[]
  vram_usage?: Record<string, unknown>
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatRequest {
  message: string
  session_id?: string
  language?: string
}

export interface ChatResponse {
  response: string
  session_id: string
  language?: string
  intent?: string
  debug?: Record<string, unknown>
}

export const api = {
  health: () => request<HealthResponse>('/health'),

  models: () => request<ModelInfo>('/models'),

  switchModel: (model: string) =>
    request<{ status: string }>('/admin/switch-model', {
      method: 'POST',
      body: JSON.stringify({ model }),
    }),

  chat: (appId: string, data: ChatRequest) =>
    request<ChatResponse>(`/${appId}/chat`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Plugin-specific endpoints
  kisanmitra: {
    schemes: (query: string) =>
      request<unknown>(`/kisanmitra/schemes?q=${encodeURIComponent(query)}`),
    mandiPrices: (commodity: string) =>
      request<unknown>(`/kisanmitra/mandi?commodity=${encodeURIComponent(commodity)}`),
    loanProducts: () => request<unknown>('/kisanmitra/loans'),
  },

  vyapaar: {
    dailySummary: () => request<unknown>('/vyapaar/bookkeeping/summary'),
    catalogue: () => request<unknown>('/vyapaar/catalogue'),
    creditReport: () => request<unknown>('/vyapaar/bookkeeping/credits'),
  },

  asha: {
    stats: () => request<unknown>('/asha_health/stats'),
  },
}
