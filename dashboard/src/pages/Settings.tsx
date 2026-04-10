import { useState } from 'react'
import { Save, RotateCcw } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SettingsState {
  apiBaseUrl: string
  defaultLanguage: string
  sessionTimeout: number
  maxConversationTurns: number
  debugMode: boolean
  autoDetectLanguage: boolean
  ollamaUrl: string
  redisUrl: string
  postgresUrl: string
}

const DEFAULT_SETTINGS: SettingsState = {
  apiBaseUrl: 'http://localhost:8000',
  defaultLanguage: 'hi',
  sessionTimeout: 30,
  maxConversationTurns: 5,
  debugMode: false,
  autoDetectLanguage: true,
  ollamaUrl: 'http://localhost:11434',
  redisUrl: 'redis://localhost:6379',
  postgresUrl: 'postgresql://localhost:5432/bharatai',
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsState>(DEFAULT_SETTINGS)
  const [saved, setSaved] = useState(false)

  const update = <K extends keyof SettingsState>(key: K, value: SettingsState[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }))
    setSaved(false)
  }

  const handleSave = () => {
    localStorage.setItem('bharatai_settings', JSON.stringify(settings))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleReset = () => {
    setSettings(DEFAULT_SETTINGS)
    localStorage.removeItem('bharatai_settings')
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Configure dashboard and platform preferences
        </p>
      </div>

      {/* General Settings */}
      <Section title="General">
        <Field label="API Base URL" hint="Backend server address">
          <input
            type="text"
            value={settings.apiBaseUrl}
            onChange={(e) => update('apiBaseUrl', e.target.value)}
            className="input-field"
          />
        </Field>
        <Field label="Default Language" hint="Fallback language for chat">
          <select
            value={settings.defaultLanguage}
            onChange={(e) => update('defaultLanguage', e.target.value)}
            className="input-field"
          >
            <option value="hi">Hindi</option>
            <option value="en">English</option>
            <option value="ta">Tamil</option>
            <option value="te">Telugu</option>
            <option value="bn">Bengali</option>
            <option value="mr">Marathi</option>
          </select>
        </Field>
        <Field label="Auto-detect Language">
          <Toggle
            checked={settings.autoDetectLanguage}
            onChange={(v) => update('autoDetectLanguage', v)}
          />
        </Field>
        <Field label="Debug Mode" hint="Show debug info in chat responses">
          <Toggle
            checked={settings.debugMode}
            onChange={(v) => update('debugMode', v)}
          />
        </Field>
      </Section>

      {/* Session Settings */}
      <Section title="Session">
        <Field label="Session Timeout (minutes)" hint="Redis session TTL">
          <input
            type="number"
            min={5}
            max={120}
            value={settings.sessionTimeout}
            onChange={(e) => update('sessionTimeout', Number(e.target.value))}
            className="input-field w-24"
          />
        </Field>
        <Field label="Max Conversation Turns" hint="Keep LLM context small">
          <input
            type="number"
            min={1}
            max={20}
            value={settings.maxConversationTurns}
            onChange={(e) => update('maxConversationTurns', Number(e.target.value))}
            className="input-field w-24"
          />
        </Field>
      </Section>

      {/* Infrastructure */}
      <Section title="Infrastructure URLs">
        <Field label="Ollama URL">
          <input
            type="text"
            value={settings.ollamaUrl}
            onChange={(e) => update('ollamaUrl', e.target.value)}
            className="input-field"
          />
        </Field>
        <Field label="Redis URL">
          <input
            type="text"
            value={settings.redisUrl}
            onChange={(e) => update('redisUrl', e.target.value)}
            className="input-field"
          />
        </Field>
        <Field label="PostgreSQL URL">
          <input
            type="text"
            value={settings.postgresUrl}
            onChange={(e) => update('postgresUrl', e.target.value)}
            className="input-field"
          />
        </Field>
      </Section>

      {/* Actions */}
      <div className="flex items-center gap-3 pt-2">
        <button
          onClick={handleSave}
          className={cn(
            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
            saved ? 'bg-success text-white' : 'bg-primary text-white hover:bg-primary/90'
          )}
        >
          <Save size={14} />
          {saved ? 'Saved!' : 'Save Settings'}
        </button>
        <button
          onClick={handleReset}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border border-border text-muted-foreground hover:text-foreground transition-colors"
        >
          <RotateCcw size={14} />
          Reset to Defaults
        </button>
      </div>

      <style>{`
        .input-field {
          width: 100%;
          padding: 0.5rem 0.75rem;
          font-size: 0.875rem;
          border: 1px solid var(--color-border);
          border-radius: 0.5rem;
          background: white;
          outline: none;
        }
        .input-field:focus {
          ring: 2px;
          ring-color: var(--color-primary);
          border-color: var(--color-primary);
          box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
        }
      `}</style>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-card border border-border rounded-lg p-5">
      <h2 className="font-medium text-foreground mb-4">{title}</h2>
      <div className="space-y-4">{children}</div>
    </div>
  )
}

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="shrink-0">
        <label className="text-sm font-medium text-foreground">{label}</label>
        {hint && <p className="text-xs text-muted-foreground mt-0.5">{hint}</p>}
      </div>
      <div className="w-64">{children}</div>
    </div>
  )
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={cn(
        'relative w-10 h-5 rounded-full transition-colors',
        checked ? 'bg-primary' : 'bg-gray-300'
      )}
    >
      <span
        className={cn(
          'absolute top-0.5 w-4 h-4 bg-white rounded-full transition-transform shadow-sm',
          checked ? 'translate-x-5' : 'translate-x-0.5'
        )}
      />
    </button>
  )
}
