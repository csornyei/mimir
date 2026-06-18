import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Spinner } from "@/components/ui/spinner";
import { useMimirStore } from "@/store";
import { MessageBubble } from "./MessageBubble";

const STICK_THRESHOLD_PX = 80;

export function MessageStream() {
    const { messages, isStreaming, conversationLoading } = useMimirStore();
    const rootRef = useRef<HTMLDivElement>(null);
    const bottomRef = useRef<HTMLDivElement>(null);
    // Whether new content should pull the view to the bottom. Stays true while
    // the user is near the bottom; flips false once they scroll up to read.
    const stickRef = useRef(true);

    const showStream = !conversationLoading && messages.length > 0;

    // Track scroll position so streaming tokens don't yank a reading user down.
    useEffect(() => {
        const viewport = rootRef.current?.querySelector<HTMLElement>(
            '[data-slot="scroll-area-viewport"]'
        );
        if (!viewport) return;
        const onScroll = () => {
            const { scrollTop, scrollHeight, clientHeight } = viewport;
            stickRef.current =
                scrollHeight - scrollTop - clientHeight < STICK_THRESHOLD_PX;
        };
        viewport.addEventListener("scroll", onScroll, { passive: true });
        return () => viewport.removeEventListener("scroll", onScroll);
    }, [showStream]);

    useEffect(() => {
        if (stickRef.current) {
            bottomRef.current?.scrollIntoView({ behavior: "smooth" });
        }
    }, [messages]);

    if (conversationLoading) {
        return (
            <div className="flex flex-1 items-center justify-center">
                <Spinner className="text-muted-foreground h-5 w-5" />
            </div>
        );
    }

    if (messages.length === 0) {
        return (
            <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center">
                <p className="font-heading text-foreground text-3xl tracking-tight">
                    Ask Mimir
                </p>
                <p className="text-muted-foreground max-w-xs text-xs">
                    Your conversations, memory, and documents stay on your own
                    hardware.
                </p>
            </div>
        );
    }

    return (
        <ScrollArea ref={rootRef} className="min-h-0 flex-1">
            <div className="mx-auto max-w-3xl space-y-4 px-4 py-4">
                {messages.map((msg) => (
                    <MessageBubble key={msg.id} message={msg} />
                ))}
                {isStreaming &&
                    messages[messages.length - 1]?.role !== "assistant" && (
                        <div className="flex justify-start">
                            <Spinner className="text-muted-foreground h-4 w-4" />
                        </div>
                    )}
                <div ref={bottomRef} />
            </div>
        </ScrollArea>
    );
}
