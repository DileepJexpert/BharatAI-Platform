import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, MessageSquare, Cpu, Heart, Scale, Wheat, IndianRupee } from 'lucide-react'
import { api, type HealthResponse, type ModelInfo } from '@/lib/api'
import { cn } from '@/lib/utils'

const domainIcons: Record<string, typeof Heart> = {
  asha_health: Heart,
  lawyer_ai: Scale,
  kisanmitra: Wheat,
  vyapaar: IndianRupee,
}

const domainColors: Record<string, string> = {
  asha_health: '#ef4444',
  lawyer_ai: '#8b5cf6',
  kisanmitra: '#22c55e',
  vyapaar: '#f59e0b',
}

const domainNames: Record<string, string> = {
  asha_health: 'ASHA Health',
  lawyer_ai: 'Lawyer AI',
  kisanmitra: 'Kisan Mitra',
  vyapaar: 'Vyapaar Sahayak',
}

export default function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [model, setModel] = useState<ModelInfo | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [h, m] = await Promise.allSettled([api.health(), api.models()])
        if (h.status === 'fulfilled') setHealth(h.value)
        if (m.status === 'fulfilled') setModel(m.value)
        if (h.status === 'rejected' && m.status === 'rejected') {
          setError('Backend unavailable. Start the server with: python -m core.api.gateway')
        }
      } catch {
        setError('Failed to connect to backend')
      }
    }
    fetchData()
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">
          BharatAI Platform overview and system health
        </p>
      </div>

      {error && (
        <div className="bg-warning/10 border border-warning/30 rounded-lg p-4">
          <p className="text-sm text-warning font-medium">Backend Offline</p>
          <p className="text-xs text-muted-foreground mt-1">{error}</p>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Activity size={20} />}
          label="API Status"
          value={health ? 'Healthy' : 'Offline'}
          color={health ? 'text-success' : 'text-danger'}
        />
        <StatCard
          icon={<Cpu size={20} />}
          label="Active Model"
          value={model?.current_model || 'Unknown'}
          color="text-primary"
        />
        <StatCard
          icon={<MessageSquare size={20} />}
          label="Plugins Loaded"
          value={String(health?.plugins?.length || 0)}
          color="text-info"
        />
        <StatCard
          icon={<Activity size={20} />}
          label="Platform"
          value={health?.platform || 'BharatAI'}
          color="text-foreground"
        />
      </div>

      {/* Domain Cards */}
      <div>
        <h2 className="text-lg font-medium text-foreground mb-3">Active Domains</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {(health?.plugins || ['asha_health', 'lawyer_ai', 'kisanmitra', 'vyapaar']).map(
            (pluginId) => {
              const Icon = domainIcons[pluginId] || Activity
              return (
                <Link
                  key={pluginId}
                  to={`/domain/${pluginId}`}
                  className="bg-card border border-border rounded-lg p-5 hover:shadow-md transition-shadow flex items-start gap-4"
                >
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: `${domainColors[pluginId]}15` }}
                  >
                    <Icon size={20} style={{ color: domainColors[pluginId] }} />
                  </div>
                  <div>
                    <h3 className="font-medium text-foreground text-sm">
                      {domainNames[pluginId] || pluginId}
                    </h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      {health?.plugins?.includes(pluginId) ? 'Active' : 'Registered'}
                    </p>
                  </div>
                </Link>
              )
            }
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-lg font-medium text-foreground mb-3">Quick Actions</h2>
        <div className="flex flex-wrap gap-3">
          <Link
            to="/chat"
            className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            Open Chat Console
          </Link>
          <Link
            to="/models"
            className="px-4 py-2 bg-secondary text-foreground rounded-lg text-sm font-medium hover:bg-secondary/80 transition-colors"
          >
            Manage Models
          </Link>
        </div>
      </div>
    </div>
  )
}

function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode
  label: string
  value: string
  color: string
}) {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <div className="flex items-center gap-3">
        <div className="text-muted-foreground">{icon}</div>
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className={cn('text-sm font-semibold mt-0.5', color)}>{value}</p>
        </div>
      </div>
    </div>
  )
}
