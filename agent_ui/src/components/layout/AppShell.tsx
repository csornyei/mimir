import { useEffect, useState } from "react";
import { Outlet, useNavigate } from "react-router";
import { List, SlidersHorizontal } from "@phosphor-icons/react";
import {
    ResizablePanelGroup,
    ResizablePanel,
    ResizableHandle,
} from "@/components/ui/resizable";
import {
    Sheet,
    SheetContent,
    SheetHeader,
    SheetTitle,
} from "@/components/ui/sheet";
import { LeftSidebar } from "./LeftSidebar";
import { RightPanel } from "./RightPanel";
import { ConfigTab } from "./ConfigTab";
import { CommandPalette } from "./CommandPalette";
import { useMimirStore } from "@/store";

export function AppShell() {
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [configOpen, setConfigOpen] = useState(false);
    const [paletteOpen, setPaletteOpen] = useState(false);
    const wsStatus = useMimirStore((s) => s.wsStatus);
    const createConversation = useMimirStore((s) => s.createConversation);
    const activeConversationId = useMimirStore((s) => s.activeConversationId);
    const conversations = useMimirStore((s) => s.conversations);
    const navigate = useNavigate();

    const activeTitle = activeConversationId
        ? (conversations.find((c) => c.id === activeConversationId)?.title ??
          "Mimir")
        : "Mimir";

    useEffect(() => {
        async function handleKeyDown(e: KeyboardEvent) {
            if (e.ctrlKey && e.key === "n") {
                e.preventDefault();
                const id = await createConversation();
                navigate(`/c/${id}`);
            }
            if (e.ctrlKey && e.key === "k") {
                e.preventDefault();
                setPaletteOpen((v) => !v);
            }
        }
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [createConversation, navigate]);

    return (
        <div className="bg-background text-foreground flex h-dvh flex-col overflow-hidden">
            <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />

            {/* Offline banner */}
            {wsStatus === "disconnected" && (
                <div className="shrink-0 border-b border-amber-800 bg-amber-900/50 px-4 py-1.5 text-center text-xs text-amber-200">
                    Disconnected — reconnecting…
                </div>
            )}

            {/* Mobile header */}
            <header className="border-border flex h-12 shrink-0 items-center justify-between gap-2 border-b px-4 pt-[env(safe-area-inset-top)] md:hidden">
                <button
                    className="text-muted-foreground hover:text-foreground shrink-0 transition-colors"
                    onClick={() => setSidebarOpen(true)}
                    aria-label="Open conversations"
                >
                    <List className="h-5 w-5" />
                </button>
                <span className="min-w-0 truncate text-sm font-semibold">
                    {activeTitle}
                </span>
                <button
                    className="text-muted-foreground hover:text-foreground shrink-0 transition-colors"
                    onClick={() => setConfigOpen(true)}
                    aria-label="Open settings"
                >
                    <SlidersHorizontal className="h-5 w-5" />
                </button>
            </header>

            {/* Desktop: three-column resizable layout.
                The responsive `hidden md:flex` lives on this wrapper, not on
                ResizablePanelGroup — the panel library forces an inline
                `display:flex` that would otherwise override `hidden`. */}
            <div className="hidden min-h-0 flex-1 md:flex">
                <ResizablePanelGroup
                    orientation="horizontal"
                    className="min-h-0 flex-1"
                >
                    <ResizablePanel
                        defaultSize="20%"
                        minSize="15%"
                        maxSize="30%"
                        className="min-w-0"
                    >
                        <LeftSidebar
                            onOpenSearch={() => setPaletteOpen(true)}
                        />
                    </ResizablePanel>
                    <ResizableHandle withHandle />
                    <ResizablePanel
                        defaultSize="55%"
                        minSize="40%"
                        className="min-w-0"
                    >
                        <div className="flex h-full flex-col overflow-hidden">
                            <Outlet />
                        </div>
                    </ResizablePanel>
                    <ResizableHandle withHandle />
                    <ResizablePanel
                        defaultSize="25%"
                        minSize="20%"
                        maxSize="35%"
                        className="min-w-0"
                    >
                        <RightPanel />
                    </ResizablePanel>
                </ResizablePanelGroup>
            </div>

            {/* Mobile: full-width middle */}
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden md:hidden">
                <Outlet />
            </div>

            {/* Mobile: left sidebar Sheet */}
            <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
                <SheetContent
                    side="left"
                    className="bg-background border-border w-72 p-0"
                >
                    <LeftSidebar
                        onOpenSearch={() => {
                            setSidebarOpen(false);
                            setPaletteOpen(true);
                        }}
                    />
                </SheetContent>
            </Sheet>

            {/* Mobile: settings Sheet (Config panel) */}
            <Sheet open={configOpen} onOpenChange={setConfigOpen}>
                <SheetContent
                    side="right"
                    className="bg-background border-border flex w-80 max-w-[85vw] flex-col p-0"
                >
                    <SheetHeader className="border-border border-b px-4 pt-4 pb-2">
                        <SheetTitle className="text-sm">Settings</SheetTitle>
                    </SheetHeader>
                    <div className="min-h-0 flex-1 overflow-hidden">
                        <ConfigTab />
                    </div>
                </SheetContent>
            </Sheet>
        </div>
    );
}
