import { useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import { Info } from "@phosphor-icons/react";
import {
    Sheet,
    SheetContent,
    SheetHeader,
    SheetTitle,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { useMimirStore } from "@/store";
import { MessageDetail } from "@/components/detail/MessageDetail";
import type { Message } from "@/types";
import { ApprovalCard } from "./ApprovalCard";
import { ThinkingBlock } from "./ThinkingBlock";
import { ToolCallCard } from "./ToolCallCard";

interface Props {
    message: Message;
}

export function MessageBubble({ message }: Props) {
    const { setSelectedMessage, selectedMessageId } = useMimirStore();
    const [sheetOpen, setSheetOpen] = useState(false);
    const isUser = message.role === "user";
    const isSelected = selectedMessageId === message.id;

    function handleClick() {
        if (!isUser) setSelectedMessage(message.id);
    }

    return (
        <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
            <div
                className={cn(
                    "max-w-[80%] space-y-2",
                    !isUser && "cursor-pointer",
                    isSelected && "ring-ring rounded-lg ring-1"
                )}
                onClick={handleClick}
            >
                {message.thinkingContent && (
                    <ThinkingBlock
                        content={message.thinkingContent}
                        tokenCount={message.metadata?.thinking_tokens ?? 0}
                        isStreaming={message.isStreaming}
                    />
                )}

                {message.toolCalls.map((tc) => (
                    <ToolCallCard key={tc.call_id} toolCall={tc} />
                ))}

                {message.approvalCard && (
                    <ApprovalCard card={message.approvalCard} />
                )}

                {(message.content || isUser || message.isStreaming) && (
                    <div
                        className={cn(
                            "relative rounded-lg px-4 py-3 text-sm",
                            isUser
                                ? "bg-primary text-primary-foreground"
                                : "bg-card border-border text-card-foreground border"
                        )}
                    >
                        {isUser ? (
                            <p className="wrap-break-word whitespace-pre-wrap">
                                {message.content}
                            </p>
                        ) : (
                            <>
                                <div className="prose prose-sm prose-invert max-w-none">
                                    <ReactMarkdown
                                        rehypePlugins={[rehypeHighlight]}
                                    >
                                        {message.content}
                                    </ReactMarkdown>
                                </div>
                                {message.isStreaming &&
                                    message.content === "" && (
                                        <span className="bg-muted-foreground/60 inline-block h-4 w-1.5 animate-pulse rounded-sm align-middle" />
                                    )}
                                {/* Mobile info button — only when metadata is available */}
                                {message.metadata && (
                                    <button
                                        className="text-muted-foreground/60 hover:text-muted-foreground absolute top-2 right-2 transition-colors md:hidden"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setSheetOpen(true);
                                        }}
                                        aria-label="Response context"
                                    >
                                        <Info className="h-4 w-4" />
                                    </button>
                                )}
                            </>
                        )}
                    </div>
                )}
            </div>

            {message.metadata && (
                <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
                    <SheetContent side="bottom" className="h-[65vh] p-0">
                        <SheetHeader className="border-border border-b px-4 pt-4 pb-2">
                            <SheetTitle className="text-sm">
                                Response Context
                            </SheetTitle>
                        </SheetHeader>
                        <MessageDetail metadata={message.metadata} />
                    </SheetContent>
                </Sheet>
            )}
        </div>
    );
}
