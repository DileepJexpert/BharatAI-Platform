import { useState, type KeyboardEvent } from 'react'
import { Send } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
  placeholder?: string
}

export default function ChatInput({ onSend, disabled, placeholder }: ChatInputProps) {
  const [input, setInput] = useState('')

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setInput('')
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex items-end gap-2 p-4 border-t border-border bg-white">
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={placeholder || 'Type a message...'}
        rows={1}
        className={cn(
          'flex-1 resize-none rounded-xl border border-border bg-secondary px-4 py-2.5 text-sm',
          'focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary',
          'placeholder:text-muted-foreground disabled:opacity-50',
          'max-h-32'
        )}
        style={{ minHeight: '42px' }}
      />
      <button
        onClick={handleSend}
        disabled={disabled || !input.trim()}
        className={cn(
          'p-2.5 rounded-xl transition-colors shrink-0',
          input.trim() && !disabled
            ? 'bg-primary text-white hover:bg-primary/90'
            : 'bg-secondary text-muted-foreground'
        )}
      >
        <Send size={18} />
      </button>
    </div>
  )
}
