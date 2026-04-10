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

export interface ProviderInfo {
  name: string
  status: 'healthy' | 'unhealthy' | 'no_api_key'
  models: string[]
  is_local: boolean
}

export interface AppModelConfig {
  provider: string
  model: string
  temperature: number
  max_tokens: number
  fallback_chain: { provider: string; model: string }[]
}

export interface TestResult {
  status: 'success' | 'error'
  response?: string
  latency_ms?: number
  message?: string
  provider: string
  model: string
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

  // Multi-provider LLM management
  llmProviders: () => request<{ providers: ProviderInfo[] }>('/admin/llm/providers'),

  llmConfig: () => request<Record<string, AppModelConfig | null>>('/admin/llm/config'),

  setLlmConfig: (appId: string, config: Partial<AppModelConfig>) =>
    request<{ message: string; config: AppModelConfig }>(`/admin/llm/config/${appId}`, {
      method: 'PUT',
      body: JSON.stringify(config),
    }),

  deleteLlmConfig: (appId: string) =>
    request<{ message: string }>(`/admin/llm/config/${appId}`, { method: 'DELETE' }),

  testLlmProvider: (provider: string, model: string, testMessage?: string) =>
    request<TestResult>('/admin/llm/test', {
      method: 'POST',
      body: JSON.stringify({ provider, model, test_message: testMessage }),
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
