import { useState } from 'react'
import { MessageSquare, Search, Filter } from 'lucide-react'
import { type DomainId, DOMAINS } from '@/types'
import { cn } from '@/lib/utils'

interface ConversationPreview {
  id: string
  domain: DomainId
  lastMessage: string
  timestamp: string
  messageCount: number
  language: string
}

const SAMPLE_CONVERSATIONS: ConversationPreview[] = [
  {
    id: '1',
    domain: 'asha_health',
    lastMessage: 'Patient Ramesh Kumar, age 45, blood pressure 140/90',
    timestamp: '2 min ago',
    messageCount: 5,
    language: 'hi',
  },
  {
    id: '2',
    domain: 'kisanmitra',
    lastMessage: 'Gehu ka bhav kya hai Azadpur mandi mein?',
    timestamp: '15 min ago',
    messageCount: 3,
    language: 'hi',
  },
  {
    id: '3',
    domain: 'vyapaar',
    lastMessage: 'Aaj ki bikri ka hisaab dikhao',
    timestamp: '1 hour ago',
    messageCount: 8,
    language: 'hi',
  },
  {
    id: '4',
    domain: 'lawyer_ai',
    lastMessage: 'What are the tenant rights under Rent Control Act?',
    timestamp: '3 hours ago',
    messageCount: 4,
    language: 'en',
  },
]

export default function Conversations() {
  const [search, setSearch] = useState('')
  const [filterDomain, setFilterDomain] = useState<string>('all')

  const filtered = SAMPLE_CONVERSATIONS.filter((c) => {
    const matchesSearch = c.lastMessage.toLowerCase().includes(search.toLowerCase())
    const matchesDomain = filterDomain === 'all' || c.domain === filterDomain
    return matchesSearch && matchesDomain
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Conversations</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Browse recent chat sessions across all domains
        </p>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <div className="flex-1 relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search conversations..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm border border-border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
        </div>
        <div className="relative">
          <Filter size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <select
            value={filterDomain}
            onChange={(e) => setFilterDomain(e.target.value)}
            className="pl-9 pr-8 py-2 text-sm border border-border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 appearance-none"
          >
            <option value="all">All Domains</option>
            {(Object.keys(DOMAINS) as DomainId[]).map((id) => (
              <option key={id} value={id}>{DOMAINS[id].name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Conversation List */}
      <div className="space-y-2">
        {filtered.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <MessageSquare size={32} className="mx-auto mb-3 opacity-50" />
            <p className="text-sm">No conversations found</p>
            <p className="text-xs mt-1">Conversations will appear here after using the Chat page</p>
          </div>
        ) : (
          filtered.map((conv) => {
            const domain = DOMAINS[conv.domain]
            return (
              <div
                key={conv.id}
                className="bg-card border border-border rounded-lg p-4 hover:shadow-sm transition-shadow cursor-pointer"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3 min-w-0">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                      style={{ backgroundColor: `${domain.color}15` }}
                    >
                      <span className="text-xs font-bold" style={{ color: domain.color }}>
                        {domain.name[0]}
                      </span>
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-foreground">{domain.name}</span>
                        <span className={cn(
                          'text-[10px] px-1.5 py-0.5 rounded',
                          'bg-secondary text-muted-foreground'
                        )}>
                          {conv.language.toUpperCase()}
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground mt-0.5 truncate">
                        {conv.lastMessage}
                      </p>
                    </div>
                  </div>
                  <div className="text-right shrink-0 ml-4">
                    <p className="text-[10px] text-muted-foreground">{conv.timestamp}</p>
                    <p className="text-[10px] text-muted-foreground mt-1">
                      {conv.messageCount} messages
                    </p>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>

      <p className="text-xs text-muted-foreground text-center">
        Note: Full conversation history requires Redis and PostgreSQL to be running
      </p>
    </div>
  )
}
