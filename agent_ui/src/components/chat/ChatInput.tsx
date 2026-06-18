import { useState } from "react";
import { PaperPlaneTilt } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useMimirStore } from "@/store";

export function ChatInput() {
    const [text, setText] = useState("");
    const { sendMessage, isStreaming, wsStatus, enterToSend } = useMimirStore();
    const disabled = isStreaming || wsStatus !== "connected";

    function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
        if (e.key !== "Enter") return;
        // Ctrl+Enter always sends. Plain Enter sends when enterToSend is on
        // (Shift+Enter inserts a newline either way).
        const send = e.ctrlKey || (enterToSend && !e.shiftKey);
        if (send) {
            e.preventDefault();
            submit();
        }
    }

    function submit() {
        const trimmed = text.trim();
        if (!trimmed || disabled) return;
        sendMessage(trimmed);
        setText("");
    }

    const hint = enterToSend
        ? "Enter to send · Shift+Enter for newline"
        : "Ctrl+Enter to send";

    return (
        <div className="border-border shrink-0 border-t px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
            <div className="mx-auto flex max-w-3xl items-end gap-2">
                <Textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={
                        wsStatus !== "connected"
                            ? "Reconnecting…"
                            : "Ask Mimir…"
                    }
                    className="max-h-50 min-h-18 resize-none text-sm"
                    disabled={disabled}
                />
                <Button
                    onClick={submit}
                    disabled={disabled || !text.trim()}
                    size="icon"
                    className="mb-0.5 shrink-0"
                    aria-label="Send message"
                >
                    <PaperPlaneTilt className="h-4 w-4" />
                </Button>
            </div>
            <p className="text-muted-foreground mx-auto mt-1 max-w-3xl text-right text-[10px]">
                {text.length > 0 ? (
                    `${text.length} chars`
                ) : (
                    <span className="hidden md:inline">{hint}</span>
                )}
            </p>
        </div>
    );
}
