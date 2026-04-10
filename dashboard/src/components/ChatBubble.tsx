import { cn } from '@/lib/utils'
import { User, Bot } from 'lucide-react'

interface ChatBubbleProps {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
}

export default function ChatBubble({ role, content, timestamp }: ChatBubbleProps) {
  const isUser = role === 'user'

  return (
    <div className={cn('flex gap-3 mb-4', isUser && 'flex-row-reverse')}>
      <div
        className={cn(
          'w-8 h-8 rounded-full flex items-center justify-center shrink-0',
          isUser ? 'bg-primary' : 'bg-secondary'
        )}
      >
        {isUser ? (
          <User size={14} className="text-white" />
        ) : (
          <Bot size={14} className="text-foreground" />
        )}
      </div>
      <div className={cn('max-w-[70%] space-y-1', isUser && 'items-end')}>
        <div
          className={cn(
            'px-4 py-2.5 rounded-2xl text-sm leading-relaxed',
            isUser
              ? 'bg-primary text-white rounded-tr-sm'
              : 'bg-secondary text-foreground rounded-tl-sm'
          )}
        >
          {content}
        </div>
        {timestamp && (
          <p className={cn('text-[10px] text-muted-foreground px-1', isUser && 'text-right')}>
            {timestamp}
          </p>
        )}
      </div>
    </div>
  )
}
