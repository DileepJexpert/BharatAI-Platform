export interface Plugin {
  id: string
  name: string
  description: string
  icon: string
  color: string
  routes: string[]
}

export interface ConversationEntry {
  id: string
  session_id: string
  app_id: string
  user_message: string
  assistant_response: string
  language: string
  timestamp: string
  intent?: string
}

export interface SystemStatus {
  api: 'online' | 'offline' | 'degraded'
  ollama: 'online' | 'offline'
  redis: 'online' | 'offline'
  postgres: 'online' | 'offline'
}

export type DomainId = 'asha_health' | 'lawyer_ai' | 'kisanmitra' | 'vyapaar'

export const DOMAINS: Record<DomainId, Plugin> = {
  asha_health: {
    id: 'asha_health',
    name: 'ASHA Health',
    description: 'Voice-based health data entry for rural health workers',
    icon: 'Heart',
    color: '#ef4444',
    routes: ['/asha_health/chat', '/asha_health/voice'],
  },
  lawyer_ai: {
    id: 'lawyer_ai',
    name: 'Lawyer AI',
    description: 'Legal document analysis and advice in Indian languages',
    icon: 'Scale',
    color: '#8b5cf6',
    routes: ['/lawyer_ai/chat', '/lawyer_ai/voice'],
  },
  kisanmitra: {
    id: 'kisanmitra',
    name: 'Kisan Mitra',
    description: 'Agricultural advisory - schemes, mandi prices, loans',
    icon: 'Wheat',
    color: '#22c55e',
    routes: ['/kisanmitra/chat', '/kisanmitra/voice', '/kisanmitra/schemes', '/kisanmitra/mandi', '/kisanmitra/loans'],
  },
  vyapaar: {
    id: 'vyapaar',
    name: 'Vyapaar Sahayak',
    description: 'Small business bookkeeping, invoicing, and catalogue',
    icon: 'IndianRupee',
    color: '#f59e0b',
    routes: ['/vyapaar/chat', '/vyapaar/voice', '/vyapaar/bookkeeping', '/vyapaar/catalogue', '/vyapaar/invoicing'],
  },
}
