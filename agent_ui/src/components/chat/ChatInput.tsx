import { useState } from "react";
import { PaperPlaneTilt } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useMimirStore } from "@/store";

export function ChatInput() {
    const [text, setText] = useState("");
    const { sendMessage, isStreaming, wsStatus } = useMimirStore();
    const disabled = isStreaming || wsStatus !== "connected";

    function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
        if (e.key === "Enter" && e.ctrlKey) {
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

    return (
        <div className="border-border shrink-0 border-t px-4 py-3">
            <div className="mx-auto flex max-w-3xl items-end gap-2">
                <Textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={
                        wsStatus !== "connected"
                            ? "Reconnecting…"
                            : "Ask Mimir… (Ctrl+Enter to send)"
                    }
                    className="max-h-50 min-h-18 resize-none text-sm"
                    disabled={disabled}
                />
                <Button
                    onClick={submit}
                    disabled={disabled || !text.trim()}
                    size="icon"
                    className="mb-0.5 shrink-0"
                >
                    <PaperPlaneTilt className="h-4 w-4" />
                </Button>
            </div>
            <p className="text-muted-foreground mx-auto mt-1 max-w-3xl text-right text-[10px]">
                {text.length > 0
                    ? `${text.length} chars`
                    : "Ctrl+Enter to send"}
            </p>
        </div>
    );
}
