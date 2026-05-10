import { useState } from "react";
import { CaretDown } from "@phosphor-icons/react";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";

interface Props {
    content: string;
    tokenCount: number;
    isStreaming: boolean;
}

export function ThinkingBlock({ content, tokenCount, isStreaming }: Props) {
    const [open, setOpen] = useState(false);

    return (
        <Collapsible open={open} onOpenChange={setOpen}>
            <CollapsibleTrigger className="bg-muted/40 border-border text-muted-foreground hover:text-foreground flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-xs transition-colors">
                <span>💭</span>
                <span>
                    {isStreaming
                        ? "Thinking…"
                        : tokenCount > 0
                          ? `Thought for ${tokenCount.toLocaleString()} tokens`
                          : "Thinking block"}
                </span>
                <CaretDown
                    className={`ml-auto h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`}
                />
            </CollapsibleTrigger>
            <CollapsibleContent>
                <pre className="text-muted-foreground bg-muted/20 border-border mt-1 max-h-64 overflow-auto rounded-lg border px-3 py-2 font-mono text-xs whitespace-pre-wrap">
                    {content}
                </pre>
            </CollapsibleContent>
        </Collapsible>
    );
}
