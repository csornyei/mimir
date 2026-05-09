import { useNavigate, Link } from 'react-router'
import { BookOpenIcon, RssIcon, PlusIcon } from '@phosphor-icons/react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useMimirStore } from '@/store'
import { ConversationItem } from '@/components/chat/ConversationItem'
import { ConversationSearch } from '@/components/chat/ConversationSearch'
import type { ConversationSummary } from '@/types'

function groupByDate(convs: ConversationSummary[]): [string, ConversationSummary[]][] {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterday = today - 86_400_000
  const thisWeek = today - 7 * 86_400_000

  const groups: Record<string, ConversationSummary[]> = {
    Today: [],
    Yesterday: [],
    'This week': [],
    Older: [],
  }

  for (const c of convs) {
    const d = new Date(c.last_active)
    const day = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
    if (day >= today) groups.Today.push(c)
    else if (day >= yesterday) groups.Yesterday.push(c)
    else if (day >= thisWeek) groups['This week'].push(c)
    else groups.Older.push(c)
  }

  return Object.entries(groups).filter(([, items]) => items.length > 0)
}

interface LeftSidebarProps {
  onOpenSearch?: () => void
}

export function LeftSidebar({ onOpenSearch }: LeftSidebarProps) {
  const navigate = useNavigate()
  const { conversations, createConversation, conversationLoading } = useMimirStore()
  const isLoading = conversations.length === 0 && conversationLoading

  async function handleNew() {
    const id = await createConversation()
    navigate(`/c/${id}`)
  }

  const groups = groupByDate(conversations)

  return (
    <div className="flex flex-col h-full border-r border-border bg-background">
      <div className="p-3 space-y-2 shrink-0">
        <Button variant="outline" className="w-full justify-start gap-2" size="sm" onClick={handleNew}>
          <PlusIcon className="w-4 h-4" />
          New conversation
        </Button>
        <ConversationSearch onClick={onOpenSearch ?? (() => { })} />
      </div>

      <ScrollArea className="flex-1 px-2">
        {isLoading ? (
          <div className="space-y-1 px-1 py-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-8 w-full rounded-md" />
            ))}
          </div>
        ) : (
          groups.map(([label, items]) => (
            <div key={label} className="mb-4">
              <p className="text-[10px] uppercase text-muted-foreground px-2 mb-1 tracking-wide">
                {label}
              </p>
              {items.map((conv) => (
                <ConversationItem key={conv.id} conversation={conv} />
              ))}
            </div>
          ))
        )}
      </ScrollArea>

      <Separator />
      <nav className="p-3 space-y-1 shrink-0">
        <Link
          to="/brief"
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground px-2 py-1.5 rounded-md hover:bg-accent transition-colors"
        >
          <BookOpenIcon className="w-4 h-4" />
          Morning Brief
        </Link>
        <Link
          to="/digest"
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground px-2 py-1.5 rounded-md hover:bg-accent transition-colors"
        >
          <RssIcon className="w-4 h-4" />
          RSS Digest
        </Link>
      </nav>
    </div>
  )
}
