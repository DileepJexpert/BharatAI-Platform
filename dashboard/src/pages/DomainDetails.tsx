import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, ExternalLink } from 'lucide-react'
import { type DomainId, DOMAINS } from '@/types'

const domainDetails: Record<string, { features: string[]; endpoints: { method: string; path: string; desc: string }[]; techNotes: string[] }> = {
  asha_health: {
    features: [
      'Voice-based health data entry for ASHA workers',
      'Patient registration and visit tracking',
      'NHM (National Health Mission) data sync',
      'Multi-language support (Hindi, Tamil, Telugu, Bengali)',
      'Low-confidence STT retry handling',
    ],
    endpoints: [
      { method: 'POST', path: '/asha_health/chat', desc: 'Chat with health assistant' },
      { method: 'POST', path: '/asha_health/voice', desc: 'Voice-based health data entry' },
    ],
    techNotes: [
      'Uses IndicWhisper medium model for STT',
      'System prompt optimized for health data extraction',
      'JSON structured output for patient records',
    ],
  },
  lawyer_ai: {
    features: [
      'Legal document analysis in Indian languages',
      'IPC/BNS section lookup and explanation',
      'FIR drafting assistance',
      'Consumer rights guidance',
      'Tenant/landlord dispute resolution',
    ],
    endpoints: [
      { method: 'POST', path: '/lawyer_ai/chat', desc: 'Chat with legal assistant' },
      { method: 'POST', path: '/lawyer_ai/voice', desc: 'Voice-based legal queries' },
    ],
    techNotes: [
      'Trained on Indian legal corpus references',
      'Disclaimer: AI-generated, not legal advice',
      'Supports IPC to BNS section mapping',
    ],
  },
  kisanmitra: {
    features: [
      'Government scheme discovery and eligibility check',
      'Mandi price lookup with Hindi commodity names',
      'Loan product comparison and EMI calculation',
      'Agmarknet price data scraping',
      'Multi-state scheme database',
    ],
    endpoints: [
      { method: 'POST', path: '/kisanmitra/chat', desc: 'Chat with agriculture assistant' },
      { method: 'POST', path: '/kisanmitra/voice', desc: 'Voice-based agriculture queries' },
      { method: 'GET', path: '/kisanmitra/schemes', desc: 'Search government schemes' },
      { method: 'GET', path: '/kisanmitra/mandi', desc: 'Get mandi prices' },
      { method: 'GET', path: '/kisanmitra/loans', desc: 'List loan products' },
    ],
    techNotes: [
      'Hindi fuzzy matching for commodity names',
      'RAG-based scheme search with scoring',
      'EMI calculator with multiple loan combinations',
    ],
  },
  vyapaar: {
    features: [
      'Double-entry bookkeeping (sale, purchase, expense)',
      'Product catalogue with stock tracking',
      'GST-compliant invoice generation',
      'Daily/monthly financial reports',
      'Credit/debit customer tracking',
      'Indian numbering format (lakh/crore)',
    ],
    endpoints: [
      { method: 'POST', path: '/vyapaar/chat', desc: 'Chat with business assistant' },
      { method: 'POST', path: '/vyapaar/voice', desc: 'Voice-based bookkeeping' },
      { method: 'POST', path: '/vyapaar/bookkeeping', desc: 'Record transactions' },
      { method: 'GET', path: '/vyapaar/catalogue', desc: 'View product catalogue' },
      { method: 'POST', path: '/vyapaar/invoicing', desc: 'Generate invoices' },
    ],
    techNotes: [
      'All amounts stored in paisa (integer math)',
      'Hindi fuzzy matching for contact names with honorific stripping',
      'GST: CGST + SGST split for invoicing',
      'Hinglish report formatting',
    ],
  },
}

export default function DomainDetails() {
  const { domainId } = useParams<{ domainId: string }>()
  const domain = DOMAINS[domainId as DomainId]
  const details = domainDetails[domainId || '']

  if (!domain || !details) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Domain not found</p>
        <Link to="/" className="text-primary text-sm mt-2 inline-block">Back to Dashboard</Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to="/" className="text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft size={20} />
        </Link>
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: `${domain.color}15` }}
          >
            <span className="text-lg font-bold" style={{ color: domain.color }}>
              {domain.name[0]}
            </span>
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-foreground">{domain.name}</h1>
            <p className="text-sm text-muted-foreground">{domain.description}</p>
          </div>
        </div>
      </div>

      {/* Features */}
      <div className="bg-card border border-border rounded-lg p-5">
        <h2 className="font-medium text-foreground mb-3">Features</h2>
        <ul className="space-y-2">
          {details.features.map((f, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
              <span className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0" style={{ backgroundColor: domain.color }} />
              {f}
            </li>
          ))}
        </ul>
      </div>

      {/* API Endpoints */}
      <div className="bg-card border border-border rounded-lg p-5">
        <h2 className="font-medium text-foreground mb-3">API Endpoints</h2>
        <div className="space-y-2">
          {details.endpoints.map((ep, i) => (
            <div key={i} className="flex items-center gap-3 text-sm">
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                ep.method === 'GET' ? 'bg-success/10 text-success' : 'bg-primary/10 text-primary'
              }`}>
                {ep.method}
              </span>
              <code className="text-xs font-mono text-foreground">{ep.path}</code>
              <span className="text-xs text-muted-foreground">— {ep.desc}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Tech Notes */}
      <div className="bg-card border border-border rounded-lg p-5">
        <h2 className="font-medium text-foreground mb-3">Technical Notes</h2>
        <ul className="space-y-2">
          {details.techNotes.map((note, i) => (
            <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
              <span className="text-muted-foreground">-</span>
              {note}
            </li>
          ))}
        </ul>
      </div>

      {/* Quick Actions */}
      <div className="flex gap-3">
        <Link
          to={`/chat`}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <ExternalLink size={14} />
          Test in Chat
        </Link>
      </div>
    </div>
  )
}
