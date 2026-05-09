import type { ResponseMetadata } from '@/types'

interface Props {
  metadata: ResponseMetadata
}

export function TokenStats({ metadata }: Props) {
  const total = metadata.thinking_tokens + metadata.response_tokens + metadata.prompt_tokens

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground uppercase tracking-wide">Tokens &amp; Latency</p>
      <div className="grid grid-cols-2 gap-2">
        {(
          [
            ['Prompt', metadata.prompt_tokens],
            ['Thinking', metadata.thinking_tokens],
            ['Response', metadata.response_tokens],
            ['Total', total],
          ] as [string, number][]
        ).map(([label, value]) => (
          <div key={label} className="px-3 py-2 rounded-lg bg-muted/30 border border-border">
            <p className="text-[10px] text-muted-foreground uppercase">{label}</p>
            <p className="text-xs font-mono text-foreground mt-0.5">{value.toLocaleString()}</p>
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-muted/30 border border-border">
        <span className="text-xs text-muted-foreground">Latency</span>
        <span className="text-xs font-mono text-foreground">
          {metadata.latency_ms.toLocaleString()} ms
        </span>
      </div>
    </div>
  )
}
