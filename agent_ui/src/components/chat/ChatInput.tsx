import { useState } from 'react'
import { PaperPlaneTilt } from '@phosphor-icons/react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useMimirStore } from '@/store'

export function ChatInput() {
  const [text, setText] = useState('')
  const { sendMessage, isStreaming, wsStatus } = useMimirStore()
  const disabled = isStreaming || wsStatus !== 'connected'

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && e.ctrlKey) {
      e.preventDefault()
      submit()
    }
  }

  function submit() {
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    sendMessage(trimmed)
    setText('')
  }

  return (
    <div className="px-4 py-3 border-t border-border shrink-0">
      <div className="max-w-3xl mx-auto flex gap-2 items-end">
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={wsStatus !== 'connected' ? 'Reconnecting…' : 'Ask Mimir… (Ctrl+Enter to send)'}
          className="resize-none min-h-18 max-h-50 text-sm"
          disabled={disabled}
        />
        <Button
          onClick={submit}
          disabled={disabled || !text.trim()}
          size="icon"
          className="shrink-0 mb-0.5"
        >
          <PaperPlaneTilt className="w-4 h-4" />
        </Button>
      </div>
      <p className="text-[10px] text-muted-foreground text-right max-w-3xl mx-auto mt-1">
        {text.length > 0 ? `${text.length} chars` : 'Ctrl+Enter to send'}
      </p>
    </div>
  )
}
