import { ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'

interface DebugPanelProps {
  data: Record<string, unknown> | null
}

export default function DebugPanel({ data }: DebugPanelProps) {
  const [expanded, setExpanded] = useState(false)

  if (!data) return null

  return (
    <div className="border-t border-border bg-gray-50">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 px-4 py-2 text-xs text-muted-foreground hover:text-foreground transition-colors w-full"
      >
        {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        Debug Info
      </button>
      {expanded && (
        <pre className="px-4 pb-3 text-xs text-muted-foreground overflow-x-auto font-mono leading-relaxed">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  )
}
