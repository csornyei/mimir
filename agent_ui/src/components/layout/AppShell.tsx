import { useEffect, useState } from "react";
import { Outlet, useNavigate } from "react-router";
import { List } from "@phosphor-icons/react";
import {
    ResizablePanelGroup,
    ResizablePanel,
    ResizableHandle,
} from "@/components/ui/resizable";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { LeftSidebar } from "./LeftSidebar";
import { RightPanel } from "./RightPanel";
import { CommandPalette } from "./CommandPalette";
import { useMimirStore } from "@/store";

export function AppShell() {
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [paletteOpen, setPaletteOpen] = useState(false);
    const wsStatus = useMimirStore((s) => s.wsStatus);
    const createConversation = useMimirStore((s) => s.createConversation);
    const navigate = useNavigate();

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
        <div className="bg-background text-foreground flex h-screen flex-col overflow-hidden">
            <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />

            {/* Offline banner */}
            {wsStatus === "disconnected" && (
                <div className="shrink-0 border-b border-amber-800 bg-amber-900/50 px-4 py-1.5 text-center text-xs text-amber-200">
                    Disconnected — reconnecting…
                </div>
            )}

            {/* Mobile header */}
            <header className="border-border flex h-12 shrink-0 items-center justify-between border-b px-4 md:hidden">
                <button
                    className="text-muted-foreground hover:text-foreground transition-colors"
                    onClick={() => setSidebarOpen(true)}
                    aria-label="Open sidebar"
                >
                    <List className="h-5 w-5" />
                </button>
                <span className="text-sm font-semibold">Mimir</span>
                {/* Right info button slot — wired in M5 */}
                <div className="w-5" />
            </header>

            {/* Desktop: three-column resizable layout */}
            <ResizablePanelGroup
                orientation="horizontal"
                className="hidden min-h-0 flex-1 md:flex"
            >
                <ResizablePanel
                    defaultSize="20%"
                    minSize="15%"
                    maxSize="30%"
                    className="min-w-0"
                >
                    <LeftSidebar onOpenSearch={() => setPaletteOpen(true)} />
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
        </div>
    );
}
