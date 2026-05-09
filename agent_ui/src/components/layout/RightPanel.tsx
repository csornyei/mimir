import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ModeSelector } from '@/components/controls/ModeSelector'
import { ThinkingSlider } from '@/components/controls/ThinkingSlider'
import { MessageDetail } from '@/components/detail/MessageDetail'
import { useMimirStore } from '@/store'

export function RightPanel() {
  const { rightPanelTab, setRightPanelTab, settings, messages, selectedMessageId } = useMimirStore()
  const selectedMessage = messages.find((m) => m.id === selectedMessageId)

  return (
    <div className="flex flex-col h-full border-l border-border bg-background">
      <Tabs
        value={rightPanelTab}
        onValueChange={(v) => setRightPanelTab(v as 'config' | 'detail')}
        className="flex flex-col h-full"
      >
        <TabsList className="mx-3 mt-3 shrink-0 w-auto">
          <TabsTrigger value="config">Config</TabsTrigger>
          <TabsTrigger value="detail">Detail</TabsTrigger>
        </TabsList>

        <TabsContent value="config" className="flex-1 min-h-0 overflow-hidden">
          <ScrollArea className="h-full">
            <div className="p-3 space-y-6">
              <ModeSelector />
              <Separator />
              <ThinkingSlider />
              <Separator />
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground uppercase tracking-wide">Parameters</p>
                <dl className="space-y-1">
                  {(
                    [
                      ['Temperature', settings.temperature],
                      ['Top-p', settings.top_p],
                      ['Min-p', settings.min_p],
                      ['Max tokens', settings.max_tokens],
                    ] as [string, number][]
                  ).map(([label, val]) => (
                    <div key={label} className="flex justify-between text-xs">
                      <dt className="text-muted-foreground">{label}</dt>
                      <dd className="font-mono text-foreground">{val}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="detail" className="flex-1 min-h-0 overflow-hidden">
          {selectedMessage?.metadata ? (
            <MessageDetail metadata={selectedMessage.metadata} />
          ) : (
            <div className="flex items-center justify-center h-full">
              <p className="text-xs text-muted-foreground text-center px-4">
                Click a response to see its context.
              </p>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
