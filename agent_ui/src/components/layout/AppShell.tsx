import { useEffect, useState } from 'react'
import { Outlet, useNavigate } from 'react-router'
import { List } from '@phosphor-icons/react'
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '@/components/ui/resizable'
import { Sheet, SheetContent } from '@/components/ui/sheet'
import { LeftSidebar } from './LeftSidebar'
import { RightPanel } from './RightPanel'
import { CommandPalette } from './CommandPalette'
import { useMimirStore } from '@/store'

export function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const wsStatus = useMimirStore((s) => s.wsStatus)
  const createConversation = useMimirStore((s) => s.createConversation)
  const navigate = useNavigate()

  useEffect(() => {
    async function handleKeyDown(e: KeyboardEvent) {
      if (e.ctrlKey && e.key === 'n') {
        e.preventDefault()
        const id = await createConversation()
        navigate(`/c/${id}`)
      }
      if (e.ctrlKey && e.key === 'k') {
        e.preventDefault()
        setPaletteOpen((v) => !v)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [createConversation, navigate])

  return (
    <div className="h-screen bg-background text-foreground flex flex-col overflow-hidden">
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />

      {/* Offline banner */}
      {wsStatus === 'disconnected' && (
        <div className="bg-amber-900/50 border-b border-amber-800 px-4 py-1.5 text-xs text-amber-200 text-center shrink-0">
          Disconnected — reconnecting…
        </div>
      )}

      {/* Mobile header */}
      <header className="md:hidden flex items-center justify-between px-4 h-12 border-b border-border shrink-0">
        <button
          className="text-muted-foreground hover:text-foreground transition-colors"
          onClick={() => setSidebarOpen(true)}
          aria-label="Open sidebar"
        >
          <List className="w-5 h-5" />
        </button>
        <span className="font-semibold text-sm">Mimir</span>
        {/* Right info button slot — wired in M5 */}
        <div className="w-5" />
      </header>

      {/* Desktop: three-column resizable layout */}
      <ResizablePanelGroup orientation="horizontal" className="hidden md:flex flex-1 min-h-0">
        <ResizablePanel defaultSize="20%" minSize="15%" maxSize="30%" className="min-w-0">
          <LeftSidebar onOpenSearch={() => setPaletteOpen(true)} />
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel defaultSize="55%" minSize="40%" className="min-w-0">
          <div className="flex flex-col h-full overflow-hidden">
            <Outlet />
          </div>
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel defaultSize="25%" minSize="20%" maxSize="35%" className="min-w-0">
          <RightPanel />
        </ResizablePanel>
      </ResizablePanelGroup>

      {/* Mobile: full-width middle */}
      <div className="md:hidden flex-1 min-h-0 flex flex-col overflow-hidden">
        <Outlet />
      </div>

      {/* Mobile: left sidebar Sheet */}
      <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
        <SheetContent side="left" className="w-72 p-0 bg-background border-border">
          <LeftSidebar onOpenSearch={() => { setSidebarOpen(false); setPaletteOpen(true) }} />
        </SheetContent>
      </Sheet>
    </div>
  )
}
