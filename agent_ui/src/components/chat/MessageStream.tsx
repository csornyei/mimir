import { useEffect, useRef } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Spinner } from '@/components/ui/spinner'
import { useMimirStore } from '@/store'
import { MessageBubble } from './MessageBubble'

export function MessageStream() {
  const { messages, isStreaming, conversationLoading } = useMimirStore()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (conversationLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Spinner className="w-5 h-5 text-muted-foreground" />
      </div>
    )
  }

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
        Start a conversation
      </div>
    )
  }

  return (
    <ScrollArea className="flex-1 min-h-0">
      <div className="px-4 py-4 space-y-4 max-w-3xl mx-auto">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isStreaming && messages[messages.length - 1]?.role !== 'assistant' && (
          <div className="flex justify-start">
            <Spinner className="w-4 h-4 text-muted-foreground" />
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  )
}
