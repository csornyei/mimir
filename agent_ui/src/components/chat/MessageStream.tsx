import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Spinner } from "@/components/ui/spinner";
import { useMimirStore } from "@/store";
import { MessageBubble } from "./MessageBubble";

export function MessageStream() {
    const { messages, isStreaming, conversationLoading } = useMimirStore();
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
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
            <div className="text-muted-foreground flex flex-1 items-center justify-center text-sm">
                Start a conversation
            </div>
        );
    }

    return (
        <ScrollArea className="min-h-0 flex-1">
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
