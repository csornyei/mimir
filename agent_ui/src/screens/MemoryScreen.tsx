import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { FloppyDiskIcon, PencilSimpleIcon, XIcon } from '@phosphor-icons/react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'

export function MemoryScreen() {
  const [content, setContent] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetch('/api/memory')
      .then((r) => r.json())
      .then((d: { content: string }) => setContent(d.content))
      .catch(() => toast.error('Failed to load memory'))
  }, [])

  function handleEdit() {
    setDraft(content ?? '')
    setEditing(true)
  }

  async function handleSave() {
    setSaving(true)
    try {
      const res = await fetch('/api/memory', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: draft }),
      })
      if (!res.ok) throw new Error(await res.text())
      setContent(draft)
      setEditing(false)
      toast.success('Memory updated')
    } catch (err) {
      console.error('[mimir] memory save failed:', err)
      toast.error('Failed to save memory')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between px-6 py-4 border-b border-border shrink-0">
        <h1 className="text-base font-semibold">Memory</h1>
        <div className="flex gap-2">
          {editing ? (
            <>
              <Button size="sm" variant="outline" onClick={() => setEditing(false)} disabled={saving}>
                <XIcon className="w-3.5 h-3.5 mr-1.5" />
                Cancel
              </Button>
              <Button size="sm" onClick={handleSave} disabled={saving}>
                <FloppyDiskIcon className="w-3.5 h-3.5 mr-1.5" />
                {saving ? 'Saving…' : 'Save'}
              </Button>
            </>
          ) : (
            <Button size="sm" variant="outline" onClick={handleEdit} disabled={content === null}>
              <PencilSimpleIcon className="w-3.5 h-3.5 mr-1.5" />
              Edit
            </Button>
          )}
        </div>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        <div className="px-6 py-4 max-w-3xl mx-auto">
          {content === null ? (
            <div className="space-y-3">
              {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-4" style={{ width: `${70 + (i % 3) * 10}%` }} />
              ))}
            </div>
          ) : editing ? (
            <Textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              className="font-mono text-sm min-h-[60vh] resize-none"
              spellCheck={false}
            />
          ) : content ? (
            <div className="prose prose-sm prose-invert max-w-none">
              <ReactMarkdown>{content}</ReactMarkdown>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground text-center pt-8">
              No memory content yet. Click Edit to add some.
            </p>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
