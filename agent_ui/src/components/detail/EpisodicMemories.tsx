import { useState } from 'react'
import { CaretDown } from '@phosphor-icons/react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import type { EpisodicMemory } from '@/types'

interface Props {
  memories: EpisodicMemory[]
}

export function EpisodicMemories({ memories }: Props) {
  if (memories.length === 0) return null

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground uppercase tracking-wide">
        Episodic Memories ({memories.length})
      </p>
      {memories.map((m, i) => (
        <EpisodicCard key={m.started_at ?? i} memory={m} />
      ))}
    </div>
  )
}

function EpisodicCard({ memory }: { memory: EpisodicMemory }) {
  const [open, setOpen] = useState(false)
  const preview = memory.summary.length > 60 ? memory.summary.substring(0, 60) + '…' : memory.summary

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="flex items-center gap-2 w-full px-3 py-2 rounded-lg bg-card/60 border border-border text-left hover:bg-muted/30 transition-colors">
        <span className="text-foreground text-xs truncate flex-1">{preview}</span>
        <span className="text-muted-foreground text-[10px] shrink-0">
          {(memory.similarity_score * 100).toFixed(0)}%
        </span>
        <CaretDown
          className={`w-3 h-3 text-muted-foreground shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="px-3 pt-1 pb-3 space-y-1">
          {memory.started_at && (
            <p className="text-[10px] text-muted-foreground">
              {new Date(memory.started_at).toLocaleDateString()}
            </p>
          )}
          <p className="text-xs text-muted-foreground leading-relaxed">{memory.summary}</p>
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}
