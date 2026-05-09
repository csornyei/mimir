import { useState } from 'react'
import { Warning } from '@phosphor-icons/react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { useMimirStore } from '@/store'
import type { ApprovalCard as ApprovalCardType } from '@/types'

interface Props {
  card: ApprovalCardType
}

export function ApprovalCard({ card }: Props) {
  const { approveAction, rejectAction } = useMimirStore()
  const [editOpen, setEditOpen] = useState(false)
  const [editedArgs, setEditedArgs] = useState(JSON.stringify(card.arguments, null, 2))
  const [editError, setEditError] = useState<string | null>(null)

  if (card.status === 'approved') {
    return (
      <div className="text-xs text-green-400 px-3 py-2 bg-green-950/30 border border-green-900/60 rounded-lg">
        ✅ Approved
      </div>
    )
  }

  if (card.status === 'rejected') {
    return (
      <div className="text-xs text-red-400 px-3 py-2 bg-red-950/30 border border-red-900/60 rounded-lg">
        ❌ Rejected
      </div>
    )
  }

  function handleConfirmEdit() {
    try {
      const parsed: unknown = JSON.parse(editedArgs)
      approveAction(card.action_id, parsed as Record<string, unknown>)
      setEditOpen(false)
    } catch {
      setEditError('Invalid JSON — fix before approving')
    }
  }

  return (
    <>
      <Alert className="bg-amber-950/20 border-amber-800/60">
        <Warning className="w-4 h-4 text-amber-400" />
        <AlertTitle className="text-amber-200 text-sm">Approval Required</AlertTitle>
        <AlertDescription className="space-y-3 mt-1">
          <p className="font-mono text-xs text-amber-300/90">{card.tool_name}</p>
          <pre className="text-xs text-amber-200/70 whitespace-pre-wrap bg-amber-950/30 rounded p-2 max-h-32 overflow-auto border border-amber-900/40 font-mono">
            {JSON.stringify(card.arguments, null, 2)}
          </pre>
          <div className="flex gap-2 flex-wrap">
            <Button size="sm" onClick={() => approveAction(card.action_id)}>
              ✅ Approve
            </Button>
            <Button size="sm" variant="outline" onClick={() => setEditOpen(true)}>
              ✏️ Edit &amp; approve
            </Button>
            <Button size="sm" variant="destructive" onClick={() => rejectAction(card.action_id)}>
              ❌ Reject
            </Button>
          </div>
        </AlertDescription>
      </Alert>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit arguments — {card.tool_name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Textarea
              value={editedArgs}
              onChange={(e) => {
                setEditedArgs(e.target.value)
                setEditError(null)
              }}
              className="font-mono text-xs min-h-50"
              spellCheck={false}
            />
            {editError && <p className="text-xs text-destructive">{editError}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleConfirmEdit}>Approve with edits</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
