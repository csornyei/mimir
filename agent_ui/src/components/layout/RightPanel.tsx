import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ModeSelector } from "@/components/controls/ModeSelector";
import { ModelSelector } from "@/components/controls/ModelSelector";
import { ThinkingSlider } from "@/components/controls/ThinkingSlider";
import { MessageDetail } from "@/components/detail/MessageDetail";
import { useMimirStore } from "@/store";

export function RightPanel() {
    const {
        rightPanelTab,
        setRightPanelTab,
        settings,
        messages,
        selectedMessageId,
    } = useMimirStore();
    const selectedMessage = messages.find((m) => m.id === selectedMessageId);

    return (
        <div className="border-border bg-background flex h-full flex-col border-l">
            <Tabs
                value={rightPanelTab}
                onValueChange={(v) =>
                    setRightPanelTab(v as "config" | "detail")
                }
                className="flex h-full flex-col"
            >
                <TabsList className="mx-3 mt-3 w-auto shrink-0">
                    <TabsTrigger value="config">Config</TabsTrigger>
                    <TabsTrigger value="detail">Detail</TabsTrigger>
                </TabsList>

                <TabsContent
                    value="config"
                    className="min-h-0 flex-1 overflow-hidden"
                >
                    <ScrollArea className="h-full">
                        <div className="space-y-6 p-3">
                            <ModelSelector />
                            <Separator />
                            <ModeSelector />
                            <Separator />
                            <ThinkingSlider />
                            <Separator />
                            <div className="space-y-2">
                                <p className="text-muted-foreground text-xs tracking-wide uppercase">
                                    Parameters
                                </p>
                                <dl className="space-y-1">
                                    {(
                                        [
                                            [
                                                "Temperature",
                                                settings.temperature,
                                            ],
                                            ["Top-p", settings.top_p],
                                            ["Min-p", settings.min_p],
                                            ["Max tokens", settings.max_tokens],
                                        ] as [string, number][]
                                    ).map(([label, val]) => (
                                        <div
                                            key={label}
                                            className="flex justify-between text-xs"
                                        >
                                            <dt className="text-muted-foreground">
                                                {label}
                                            </dt>
                                            <dd className="text-foreground font-mono">
                                                {val}
                                            </dd>
                                        </div>
                                    ))}
                                </dl>
                            </div>
                        </div>
                    </ScrollArea>
                </TabsContent>

                <TabsContent
                    value="detail"
                    className="min-h-0 flex-1 overflow-hidden"
                >
                    {selectedMessage?.metadata ? (
                        <MessageDetail metadata={selectedMessage.metadata} />
                    ) : (
                        <div className="flex h-full items-center justify-center">
                            <p className="text-muted-foreground px-4 text-center text-xs">
                                Click a response to see its context.
                            </p>
                        </div>
                    )}
                </TabsContent>
            </Tabs>
        </div>
    );
}
