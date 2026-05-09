import { useState } from 'react'
import { CaretDown } from '@phosphor-icons/react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'

interface Props {
  content: string
  tokenCount: number
  isStreaming: boolean
}

export function ThinkingBlock({ content, tokenCount, isStreaming }: Props) {
  const [open, setOpen] = useState(false)

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="flex items-center gap-2 w-full text-left px-3 py-2 rounded-lg bg-muted/40 border border-border text-muted-foreground text-xs hover:text-foreground transition-colors">
        <span>💭</span>
        <span>
          {isStreaming
            ? 'Thinking…'
            : tokenCount > 0
              ? `Thought for ${tokenCount.toLocaleString()} tokens`
              : 'Thinking block'}
        </span>
        <CaretDown
          className={`ml-auto w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <pre className="mt-1 px-3 py-2 text-xs font-mono text-muted-foreground bg-muted/20 rounded-lg border border-border whitespace-pre-wrap overflow-auto max-h-64">
          {content}
        </pre>
      </CollapsibleContent>
    </Collapsible>
  )
}
