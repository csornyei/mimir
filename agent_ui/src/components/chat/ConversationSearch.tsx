import { MagnifyingGlass } from '@phosphor-icons/react'

interface Props {
  onClick: () => void
}

export function ConversationSearch({ onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 w-full px-2 py-1.5 text-xs text-muted-foreground rounded-md border border-border bg-background hover:bg-accent hover:text-foreground transition-colors"
    >
      <MagnifyingGlass className="w-3.5 h-3.5 shrink-0" />
      <span className="flex-1 text-left">Search…</span>
      <kbd className="hidden sm:inline-flex items-center gap-0.5 px-1 py-0.5 text-[10px] font-mono bg-muted rounded border border-border leading-none">
        ⌃K
      </kbd>
    </button>
  )
}
