import { useEffect, useState } from 'react'
import { Cpu, RefreshCw, Check, AlertCircle } from 'lucide-react'
import { api, type ModelInfo } from '@/lib/api'
import { cn } from '@/lib/utils'

const AVAILABLE_MODELS = [
  { id: 'llama3.2:3b-instruct-q4_0', name: 'LLaMA 3.2 3B', vram: '~2.4GB', description: 'Default model - balanced quality and speed' },
  { id: 'llama3.2:1b-instruct-q4_0', name: 'LLaMA 3.2 1B', vram: '~1.2GB', description: 'Lighter model for lower VRAM usage' },
  { id: 'gemma2:2b', name: 'Gemma 2 2B', vram: '~1.8GB', description: 'Google Gemma - good for multilingual' },
  { id: 'phi3:mini', name: 'Phi-3 Mini', vram: '~2.0GB', description: 'Microsoft Phi-3 - strong reasoning' },
]

export default function Models() {
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null)
  const [switching, setSwitching] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    fetchModels()
  }, [])

  const fetchModels = async () => {
    try {
      const data = await api.models()
      setModelInfo(data)
      setError(null)
    } catch {
      setError('Failed to fetch model info. Is the backend running?')
    }
  }

  const handleSwitch = async (modelId: string) => {
    setSwitching(modelId)
    setError(null)
    setSuccess(null)
    try {
      await api.switchModel(modelId)
      setSuccess(`Switched to ${modelId}`)
      await fetchModels()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to switch model')
    } finally {
      setSwitching(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Models</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage LLM models for the platform (8GB VRAM budget)
          </p>
        </div>
        <button
          onClick={fetchModels}
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

      {/* Current Model */}
      <div className="bg-card border border-border rounded-lg p-5">
        <div className="flex items-center gap-3 mb-3">
          <Cpu size={20} className="text-primary" />
          <h2 className="font-medium text-foreground">Current Model</h2>
        </div>
        <div className="bg-primary/5 rounded-lg p-4">
          <p className="text-sm font-mono font-medium text-foreground">
            {modelInfo?.current_model || 'Not connected'}
          </p>
        </div>
      </div>

      {/* Available Models */}
      <div>
        <h2 className="font-medium text-foreground mb-3">Available Models</h2>
        <div className="grid gap-3">
          {AVAILABLE_MODELS.map((m) => {
            const isCurrent = modelInfo?.current_model === m.id
            const isSwitching = switching === m.id
            return (
              <div
                key={m.id}
                className={cn(
                  'bg-card border rounded-lg p-4 flex items-center justify-between',
                  isCurrent ? 'border-primary/50 bg-primary/5' : 'border-border'
                )}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-medium text-foreground">{m.name}</h3>
                    {isCurrent && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-medium">
                        ACTIVE
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{m.description}</p>
                  <p className="text-xs text-muted-foreground mt-0.5 font-mono">
                    VRAM: {m.vram}
                  </p>
                </div>
                {!isCurrent && (
                  <button
                    onClick={() => handleSwitch(m.id)}
                    disabled={isSwitching}
                    className={cn(
                      'px-3 py-1.5 text-xs font-medium rounded-lg transition-colors',
                      isSwitching
                        ? 'bg-secondary text-muted-foreground'
                        : 'bg-primary text-white hover:bg-primary/90'
                    )}
                  >
                    {isSwitching ? 'Switching...' : 'Switch'}
                  </button>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* VRAM Info */}
      <div className="bg-card border border-border rounded-lg p-5">
        <h2 className="font-medium text-foreground mb-2">VRAM Budget</h2>
        <div className="space-y-2 text-sm text-muted-foreground">
          <p>Total: 8GB (7GB usable) - RTX 4060</p>
          <div className="w-full bg-secondary rounded-full h-3 overflow-hidden">
            <div className="h-full bg-primary rounded-full" style={{ width: '45%' }} />
          </div>
          <div className="flex justify-between text-xs">
            <span>LLM: ~2.4GB</span>
            <span>STT (on-demand): ~1.5GB</span>
            <span>Free: ~3.1GB</span>
          </div>
        </div>
      </div>
    </div>
  )
}
