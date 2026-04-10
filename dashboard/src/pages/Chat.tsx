import { useState, useRef, useEffect } from 'react'
import { api, type ChatResponse } from '@/lib/api'
import { type DomainId, DOMAINS } from '@/types'
import ChatBubble from '@/components/ChatBubble'
import ChatInput from '@/components/ChatInput'
import DebugPanel from '@/components/DebugPanel'
import { cn } from '@/lib/utils'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  debug?: Record<string, unknown>
}

export default function Chat() {
  const [selectedDomain, setSelectedDomain] = useState<DomainId>('asha_health')
  const [messages, setMessages] = useState<Message[]>([])
  const [sessionId, setSessionId] = useState<string | undefined>()
  const [loading, setLoading] = useState(false)
  const [language, setLanguage] = useState('hi')
  const [lastDebug, setLastDebug] = useState<Record<string, unknown> | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const handleSend = async (message: string) => {
    const now = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
    setMessages((prev) => [...prev, { role: 'user', content: message, timestamp: now }])
    setLoading(true)

    try {
      const response: ChatResponse = await api.chat(selectedDomain, {
        message,
        session_id: sessionId,
        language,
      })
      setSessionId(response.session_id)
      setLastDebug(response.debug || null)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: response.response,
          timestamp: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
          debug: response.debug,
        },
      ])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${err instanceof Error ? err.message : 'Failed to get response'}`,
          timestamp: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleClear = () => {
    setMessages([])
    setSessionId(undefined)
    setLastDebug(null)
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Header Controls */}
      <div className="flex items-center justify-between pb-4 border-b border-border">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Chat Testing</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Test conversations with any domain plugin
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Language selector */}
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="text-sm border border-border rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-primary/20"
          >
            <option value="hi">Hindi</option>
            <option value="en">English</option>
            <option value="ta">Tamil</option>
            <option value="te">Telugu</option>
            <option value="bn">Bengali</option>
            <option value="mr">Marathi</option>
          </select>

          {/* Clear button */}
          <button
            onClick={handleClear}
            className="text-sm px-3 py-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground transition-colors"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Domain selector tabs */}
      <div className="flex gap-1 py-3 border-b border-border overflow-x-auto">
        {(Object.keys(DOMAINS) as DomainId[]).map((id) => {
          const domain = DOMAINS[id]
          return (
            <button
              key={id}
              onClick={() => {
                setSelectedDomain(id)
                handleClear()
              }}
              className={cn(
                'px-4 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors',
                selectedDomain === id
                  ? 'text-white'
                  : 'bg-secondary text-muted-foreground hover:text-foreground'
              )}
              style={
                selectedDomain === id ? { backgroundColor: domain.color } : undefined
              }
            >
              {domain.name}
            </button>
          )
        })}
      </div>

      {/* Messages Area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto py-4 px-2">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4"
              style={{ backgroundColor: `${DOMAINS[selectedDomain].color}15` }}
            >
              <span className="text-2xl font-bold" style={{ color: DOMAINS[selectedDomain].color }}>
                {DOMAINS[selectedDomain].name[0]}
              </span>
            </div>
            <h3 className="text-lg font-medium text-foreground">
              {DOMAINS[selectedDomain].name}
            </h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-md">
              {DOMAINS[selectedDomain].description}
            </p>
            <p className="text-xs text-muted-foreground mt-3">
              Type a message to start testing this domain
            </p>
          </div>
        ) : (
          messages.map((msg, i) => (
            <ChatBubble key={i} role={msg.role} content={msg.content} timestamp={msg.timestamp} />
          ))
        )}
        {loading && (
          <div className="flex gap-3 mb-4">
            <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center">
              <div className="flex gap-1">
                <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Debug Panel */}
      <DebugPanel data={lastDebug} />

      {/* Input */}
      <ChatInput
        onSend={handleSend}
        disabled={loading}
        placeholder={`Message ${DOMAINS[selectedDomain].name}...`}
      />
    </div>
  )
}
