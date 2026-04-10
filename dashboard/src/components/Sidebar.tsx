import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  MessageSquare,
  History,
  Cpu,
  Settings,
  Heart,
  Scale,
  Wheat,
  IndianRupee,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useState } from 'react'

const mainNav = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/chat', icon: MessageSquare, label: 'Chat Testing' },
  { to: '/conversations', icon: History, label: 'Conversations' },
  { to: '/models', icon: Cpu, label: 'Models' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

const domainNav = [
  { to: '/domain/asha_health', icon: Heart, label: 'ASHA Health', color: '#ef4444' },
  { to: '/domain/lawyer_ai', icon: Scale, label: 'Lawyer AI', color: '#8b5cf6' },
  { to: '/domain/kisanmitra', icon: Wheat, label: 'Kisan Mitra', color: '#22c55e' },
  { to: '/domain/vyapaar', icon: IndianRupee, label: 'Vyapaar Sahayak', color: '#f59e0b' },
]

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <aside
      className={cn(
        'bg-sidebar border-r border-border flex flex-col h-screen sticky top-0 transition-all duration-200',
        collapsed ? 'w-16' : 'w-60'
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 h-14 border-b border-border">
        <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center shrink-0">
          <span className="text-white font-bold text-sm">B</span>
        </div>
        {!collapsed && (
          <span className="font-semibold text-foreground text-sm whitespace-nowrap">
            BharatAI Platform
          </span>
        )}
      </div>

      {/* Main Navigation */}
      <nav className="flex-1 py-3 px-2 space-y-1 overflow-y-auto">
        <div className={cn('text-xs font-medium text-muted-foreground mb-2', collapsed ? 'px-1' : 'px-2')}>
          {!collapsed && 'MAIN'}
        </div>
        {mainNav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary font-medium'
                  : 'text-sidebar-foreground hover:bg-secondary'
              )
            }
          >
            <item.icon size={18} className="shrink-0" />
            {!collapsed && <span>{item.label}</span>}
          </NavLink>
        ))}

        <div className={cn('text-xs font-medium text-muted-foreground mt-5 mb-2', collapsed ? 'px-1' : 'px-2')}>
          {!collapsed && 'DOMAINS'}
        </div>
        {domainNav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary font-medium'
                  : 'text-sidebar-foreground hover:bg-secondary'
              )
            }
          >
            <item.icon size={18} style={{ color: item.color }} className="shrink-0" />
            {!collapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-center h-10 border-t border-border text-muted-foreground hover:text-foreground transition-colors"
      >
        {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      </button>
    </aside>
  )
}
