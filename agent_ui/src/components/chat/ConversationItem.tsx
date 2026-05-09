import { useState } from 'react'
import { useNavigate } from 'react-router'
import { DotsThree, Trash, PencilSimple } from '@phosphor-icons/react'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useMimirStore } from '@/store'
import type { ConversationSummary } from '@/types'
import { cn } from '@/lib/utils'

interface Props {
  conversation: ConversationSummary
}

export function ConversationItem({ conversation }: Props) {
  const navigate = useNavigate()
  const { activeConversationId, deleteConversation, renameConversation } = useMimirStore()
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [renameOpen, setRenameOpen] = useState(false)
  const [draftTitle, setDraftTitle] = useState('')
  const isActive = activeConversationId === conversation.id

  const title =
    conversation.title ??
    conversation.id.split('|')[1]?.substring(0, 24) ??
    conversation.id.substring(0, 24)

  function openRename(e: React.MouseEvent) {
    e.stopPropagation()
    setDraftTitle(conversation.title ?? '')
    setRenameOpen(true)
  }

  function handleRename() {
    const trimmed = draftTitle.trim()
    if (trimmed) renameConversation(conversation.id, trimmed)
    setRenameOpen(false)
  }

  return (
    <>
      <div
        className={cn(
          'group flex items-center justify-between px-2 py-1.5 rounded-md cursor-pointer text-sm transition-colors',
          isActive
            ? 'bg-accent text-accent-foreground'
            : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'
        )}
        onClick={() => navigate(`/c/${conversation.id}`)}
      >
        <span className="truncate flex-1 min-w-0">{title}</span>

        <DropdownMenu>
          <DropdownMenuTrigger
            className="opacity-0 group-hover:opacity-100 shrink-0 p-0.5 rounded hover:bg-accent ml-1"
            onClick={(e) => e.stopPropagation()}
            aria-label="Conversation options"
          >
            <DotsThree className="w-4 h-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-40">
            <DropdownMenuItem className="text-xs" onClick={openRename}>
              <PencilSimple className="w-3.5 h-3.5 mr-2" />
              Rename
            </DropdownMenuItem>
            <DropdownMenuItem
              className="text-destructive focus:text-destructive focus:bg-destructive/10 text-xs"
              onClick={(e) => { e.stopPropagation(); setDeleteOpen(true) }}
            >
              <Trash className="w-3.5 h-3.5 mr-2" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename conversation</DialogTitle>
          </DialogHeader>
          <Input
            value={draftTitle}
            onChange={(e) => setDraftTitle(e.target.value)}
            placeholder="Conversation title"
            onKeyDown={(e) => { if (e.key === 'Enter') handleRename() }}
            autoFocus
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleRename} disabled={!draftTitle.trim()}>
              Rename
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete conversation?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">This cannot be undone.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={async () => {
                await deleteConversation(conversation.id)
                setDeleteOpen(false)
                navigate('/')
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
