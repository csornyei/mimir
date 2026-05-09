import { useState } from 'react'
import { CaretDown, Wrench } from '@phosphor-icons/react'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import type { ToolCall } from '@/types'

interface Props {
  toolCall: ToolCall
}

export function ToolCallCard({ toolCall }: Props) {
  const [open, setOpen] = useState(false)

  const firstArg = Object.entries(toolCall.arguments)[0]
  const preview = firstArg
    ? `${firstArg[0]}: ${JSON.stringify(firstArg[1]).slice(0, 40)}`
    : ''

  return (
    <Card className="bg-card/60 border-border text-xs overflow-hidden">
      <Collapsible open={open} onOpenChange={setOpen}>
        <CollapsibleTrigger className="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-muted/30 transition-colors">
          <Wrench className="w-3 h-3 text-muted-foreground shrink-0" />
          <span className="font-mono text-foreground">{toolCall.name}</span>
          {preview && (
            <span className="text-muted-foreground truncate flex-1 min-w-0">{preview}</span>
          )}
          {toolCall.result === null ? (
            <Badge variant="outline" className="ml-auto text-[10px] border-border shrink-0">
              running
            </Badge>
          ) : (
            <Badge variant="outline" className="ml-auto text-[10px] border-border text-green-500 shrink-0">
              done
            </Badge>
          )}
          <CaretDown
            className={`w-3 h-3 text-muted-foreground shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
          />
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="px-3 pb-3 space-y-2 border-t border-border pt-2">
            <div>
              <p className="text-muted-foreground uppercase tracking-wide text-[10px] mb-1">
                Arguments
              </p>
              <pre className="font-mono text-muted-foreground whitespace-pre-wrap break-all leading-relaxed">
                {JSON.stringify(toolCall.arguments, null, 2)}
              </pre>
            </div>
            {toolCall.result !== null && (
              <div>
                <p className="text-muted-foreground uppercase tracking-wide text-[10px] mb-1">
                  Result
                </p>
                <pre className="font-mono text-muted-foreground whitespace-pre-wrap break-all max-h-40 overflow-auto leading-relaxed">
                  {toolCall.result}
                </pre>
              </div>
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  )
}
