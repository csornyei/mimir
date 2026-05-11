import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConfigTab } from "@/components/layout/ConfigTab";
import { DetailTab } from "@/components/layout/DetailTab";
import { useMimirStore } from "@/store";

export function RightPanel() {
    const { rightPanelTab, setRightPanelTab } = useMimirStore();

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
                    <ConfigTab />
                </TabsContent>

                <TabsContent
                    value="detail"
                    className="min-h-0 flex-1 overflow-hidden"
                >
                    <DetailTab />
                </TabsContent>
            </Tabs>
        </div>
    );
}
