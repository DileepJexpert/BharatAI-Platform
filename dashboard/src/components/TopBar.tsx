import { useEffect, useState } from 'react'
import { Circle } from 'lucide-react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

export default function TopBar() {
  const [status, setStatus] = useState<'online' | 'offline' | 'checking'>('checking')
  const [plugins, setPlugins] = useState<string[]>([])

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const data = await api.health()
        setStatus(data.status === 'healthy' ? 'online' : 'offline')
        setPlugins(data.plugins || [])
      } catch {
        setStatus('offline')
      }
    }
    checkHealth()
    const interval = setInterval(checkHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  return (
    <header className="h-14 border-b border-border bg-white flex items-center justify-between px-6 sticky top-0 z-10">
      <div className="flex items-center gap-4">
        <h2 className="text-sm font-medium text-foreground">Admin Dashboard</h2>
      </div>

      <div className="flex items-center gap-4">
        {/* Plugin count */}
        <span className="text-xs text-muted-foreground">
          {plugins.length} plugin{plugins.length !== 1 ? 's' : ''} loaded
        </span>

        {/* Status indicator */}
        <div className="flex items-center gap-2">
          <Circle
            size={8}
            className={cn(
              'fill-current',
              status === 'online' && 'text-success',
              status === 'offline' && 'text-danger',
              status === 'checking' && 'text-warning'
            )}
          />
          <span className="text-xs text-muted-foreground capitalize">{status}</span>
        </div>
      </div>
    </header>
  )
}
