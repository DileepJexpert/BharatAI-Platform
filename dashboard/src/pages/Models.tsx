import { useEffect, useState } from 'react'
import {
  Cpu, RefreshCw, Check, AlertCircle, Play, Save, X, Server, Cloud,
} from 'lucide-react'
import { api, type ProviderInfo, type AppModelConfig, type TestResult } from '@/lib/api'
import { type DomainId, DOMAINS } from '@/types'
import { cn } from '@/lib/utils'

export default function Models() {
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [configs, setConfigs] = useState<Record<string, AppModelConfig | null>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<TestResult | null>(null)
  const [testing, setTesting] = useState<string | null>(null)
  const [saving, setSaving] = useState<string | null>(null)

  // Editable state per app
  const [edits, setEdits] = useState<Record<string, { provider: string; model: string }>>({})

  useEffect(() => {
    fetchAll()
  }, [])

  const fetchAll = async () => {
    setLoading(true)
    setError(null)
    try {
      const [p, c] = await Promise.allSettled([api.llmProviders(), api.llmConfig()])
      if (p.status === 'fulfilled') setProviders(p.value.providers)
      if (c.status === 'fulfilled') setConfigs(c.value)
      if (p.status === 'rejected' && c.status === 'rejected') {
        setError('Backend unavailable. Start the server to manage LLM providers.')
      }
    } catch {
      setError('Failed to load provider data')
    } finally {
      setLoading(false)
    }
  }

  const handleTest = async (providerName: string, model: string) => {
    setTesting(`${providerName}/${model}`)
    setTestResult(null)
    try {
      const result = await api.testLlmProvider(providerName, model, 'Namaste, reply in one short sentence.')
      setTestResult(result)
    } catch (err) {
      setTestResult({ status: 'error', message: String(err), provider: providerName, model })
    } finally {
      setTesting(null)
    }
  }

  const handleSave = async (appId: string) => {
    const edit = edits[appId]
    if (!edit) return
    setSaving(appId)
    setError(null)
    setSuccess(null)
    try {
      await api.setLlmConfig(appId, { provider: edit.provider, model: edit.model })
      setSuccess(`Updated ${appId}: ${edit.provider}/${edit.model} — effective immediately`)
      setEdits((prev) => { const n = { ...prev }; delete n[appId]; return n })
      await fetchAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(null)
    }
  }

  const handleRevert = async (appId: string) => {
    setError(null)
    try {
      await api.deleteLlmConfig(appId)
      setSuccess(`${appId} reverted to default`)
      await fetchAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Revert failed')
    }
  }

  const getModelsForProvider = (providerName: string): string[] => {
    const p = providers.find((x) => x.name === providerName)
    return p?.models || []
  }

  const allAppIds = ['default', ...Object.keys(DOMAINS)] as const

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">LLM Models & Providers</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Configure which LLM provider each domain uses. Changes take effect immediately.
          </p>
        </div>
        <button
          onClick={fetchAll}
          className="flex items-center gap-2 px-3 py-1.5 text-sm border border-border rounded-lg hover:bg-secondary transition-colors"
        >
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 bg-danger/10 border border-danger/30 rounded-lg p-3">
          <AlertCircle size={16} className="text-danger shrink-0" />
          <p className="text-sm text-danger">{error}</p>
        </div>
      )}
      {success && (
        <div className="flex items-center gap-2 bg-success/10 border border-success/30 rounded-lg p-3">
          <Check size={16} className="text-success shrink-0" />
          <p className="text-sm text-success">{success}</p>
        </div>
      )}

      {/* Provider Cards */}
      <div>
        <h2 className="font-medium text-foreground mb-3">Registered Providers</h2>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading providers...</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {providers.map((p) => (
              <div key={p.name} className="bg-card border border-border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {p.is_local ? (
                      <Server size={16} className="text-primary" />
                    ) : (
                      <Cloud size={16} className="text-info" />
                    )}
                    <h3 className="text-sm font-medium text-foreground">{p.name}</h3>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span
                      className={cn(
                        'text-[10px] px-1.5 py-0.5 rounded font-medium',
                        p.is_local ? 'bg-primary/10 text-primary' : 'bg-info/10 text-info'
                      )}
                    >
                      {p.is_local ? 'LOCAL GPU' : 'CLOUD API'}
                    </span>
                    <div
                      className={cn(
                        'w-2 h-2 rounded-full',
                        p.status === 'healthy' ? 'bg-success' : 'bg-danger'
                      )}
                    />
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mb-2">
                  {p.models.length} model{p.models.length !== 1 ? 's' : ''}: {p.models.slice(0, 3).join(', ')}
                  {p.models.length > 3 && ` +${p.models.length - 3} more`}
                </p>
                {p.status === 'healthy' && p.models.length > 0 && (
                  <button
                    onClick={() => handleTest(p.name, p.models[0])}
                    disabled={testing !== null}
                    className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors"
                  >
                    <Play size={10} />
                    Test {p.models[0]}
                  </button>
                )}
              </div>
            ))}
            {providers.length === 0 && !loading && (
              <p className="text-sm text-muted-foreground col-span-3">No providers registered</p>
            )}
          </div>
        )}
      </div>

      {/* Test Result */}
      {testResult && (
        <div
          className={cn(
            'border rounded-lg p-4',
            testResult.status === 'success' ? 'bg-success/5 border-success/30' : 'bg-danger/5 border-danger/30'
          )}
        >
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium">
              Test: {testResult.provider}/{testResult.model}
            </h3>
            <button onClick={() => setTestResult(null)} className="text-muted-foreground">
              <X size={14} />
            </button>
          </div>
          {testResult.status === 'success' ? (
            <>
              <p className="text-sm text-foreground">{testResult.response}</p>
              <p className="text-xs text-muted-foreground mt-1">Latency: {testResult.latency_ms}ms</p>
            </>
          ) : (
            <p className="text-sm text-danger">{testResult.message}</p>
          )}
        </div>
      )}

      {/* Per-App Configuration */}
      <div>
        <h2 className="font-medium text-foreground mb-3">Per-App Configuration</h2>
        <p className="text-xs text-muted-foreground mb-3">
          Each domain can use a different provider and model. Apps without config use the default.
        </p>
        <div className="space-y-2">
          {allAppIds.map((appId) => {
            const config = configs[appId]
            const isDefault = appId === 'default'
            const edit = edits[appId]
            const currentProvider = edit?.provider || config?.provider || ''
            const currentModel = edit?.model || config?.model || ''
            const domainInfo = !isDefault ? DOMAINS[appId as DomainId] : null
            const hasCustomConfig = !isDefault && config !== null

            return (
              <div
                key={appId}
                className={cn(
                  'bg-card border rounded-lg p-4',
                  isDefault ? 'border-primary/30' : 'border-border'
                )}
              >
                <div className="flex items-center justify-between flex-wrap gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    {isDefault ? (
                      <Cpu size={16} className="text-primary shrink-0" />
                    ) : (
                      <div
                        className="w-6 h-6 rounded flex items-center justify-center shrink-0 text-[10px] font-bold text-white"
                        style={{ backgroundColor: domainInfo?.color || '#94a3b8' }}
                      >
                        {(domainInfo?.name || appId)[0]}
                      </div>
                    )}
                    <div>
                      <span className="text-sm font-medium text-foreground">
                        {isDefault ? 'Default (all apps)' : domainInfo?.name || appId}
                      </span>
                      {!isDefault && !hasCustomConfig && (
                        <span className="text-[10px] ml-2 text-muted-foreground">(using default)</span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    {/* Provider dropdown */}
                    <select
                      value={currentProvider}
                      onChange={(e) => {
                        const newProvider = e.target.value
                        const models = getModelsForProvider(newProvider)
                        setEdits((prev) => ({
                          ...prev,
                          [appId]: { provider: newProvider, model: models[0] || '' },
                        }))
                      }}
                      className="text-xs border border-border rounded-md px-2 py-1 bg-white"
                    >
                      <option value="">Select provider</option>
                      {providers.map((p) => (
                        <option key={p.name} value={p.name}>
                          {p.name} {p.status !== 'healthy' ? '(offline)' : ''}
                        </option>
                      ))}
                    </select>

                    {/* Model dropdown */}
                    <select
                      value={currentModel}
                      onChange={(e) =>
                        setEdits((prev) => ({
                          ...prev,
                          [appId]: { provider: currentProvider, model: e.target.value },
                        }))
                      }
                      className="text-xs border border-border rounded-md px-2 py-1 bg-white min-w-[180px]"
                    >
                      <option value="">Select model</option>
                      {getModelsForProvider(currentProvider).map((m) => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>

                    {/* Save button */}
                    {edit && (
                      <button
                        onClick={() => handleSave(appId)}
                        disabled={saving === appId || !edit.provider || !edit.model}
                        className="flex items-center gap-1 px-2.5 py-1 text-xs bg-primary text-white rounded-md hover:bg-primary/90 transition-colors"
                      >
                        <Save size={12} />
                        {saving === appId ? 'Saving...' : 'Save'}
                      </button>
                    )}

                    {/* Revert to default (for non-default apps with custom config) */}
                    {hasCustomConfig && !isDefault && (
                      <button
                        onClick={() => handleRevert(appId)}
                        className="text-xs text-muted-foreground hover:text-danger transition-colors"
                        title="Revert to default"
                      >
                        <X size={14} />
                      </button>
                    )}
                  </div>
                </div>

                {/* Show current config details */}
                {config && (
                  <div className="mt-2 flex items-center gap-3 text-[10px] text-muted-foreground">
                    <span>
                      temp: {config.temperature}
                    </span>
                    <span>max_tokens: {config.max_tokens}</span>
                    {config.fallback_chain?.length > 0 && (
                      <span>
                        fallback: {config.fallback_chain.map((f) => `${f.provider}/${f.model}`).join(' → ')}
                      </span>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* VRAM Info */}
      <div className="bg-card border border-border rounded-lg p-5">
        <h2 className="font-medium text-foreground mb-2">VRAM Budget (Local GPU)</h2>
        <div className="space-y-2 text-sm text-muted-foreground">
          <p>Total: 8GB (7GB usable) — RTX 4060</p>
          <div className="w-full bg-secondary rounded-full h-3 overflow-hidden">
            <div className="h-full bg-primary rounded-full" style={{ width: '45%' }} />
          </div>
          <div className="flex justify-between text-xs">
            <span>LLM: ~2.4GB</span>
            <span>STT (on-demand): ~1.5GB</span>
            <span>Free: ~3.1GB</span>
          </div>
          <p className="text-xs mt-2">
            Note: Cloud providers (Groq, Gemini, Claude) use no local VRAM.
          </p>
        </div>
      </div>
    </div>
  )
}
