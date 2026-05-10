import { useState } from "react";
import { CaretDown } from "@phosphor-icons/react";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";
import type { EpisodicMemory } from "@/types";

interface Props {
    memories: EpisodicMemory[];
}

export function EpisodicMemories({ memories }: Props) {
    if (memories.length === 0) return null;

    return (
        <div className="space-y-2">
            <p className="text-muted-foreground text-xs tracking-wide uppercase">
                Episodic Memories ({memories.length})
            </p>
            {memories.map((m, i) => (
                <EpisodicCard key={m.started_at ?? i} memory={m} />
            ))}
        </div>
    );
}

function EpisodicCard({ memory }: { memory: EpisodicMemory }) {
    const [open, setOpen] = useState(false);
    const preview =
        memory.summary.length > 60
            ? memory.summary.substring(0, 60) + "…"
            : memory.summary;

    return (
        <Collapsible open={open} onOpenChange={setOpen}>
            <CollapsibleTrigger className="bg-card/60 border-border hover:bg-muted/30 flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left transition-colors">
                <span className="text-foreground flex-1 truncate text-xs">
                    {preview}
                </span>
                <span className="text-muted-foreground shrink-0 text-[10px]">
                    {(memory.similarity_score * 100).toFixed(0)}%
                </span>
                <CaretDown
                    className={`text-muted-foreground h-3 w-3 shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
                />
            </CollapsibleTrigger>
            <CollapsibleContent>
                <div className="space-y-1 px-3 pt-1 pb-3">
                    {memory.started_at && (
                        <p className="text-muted-foreground text-[10px]">
                            {new Date(memory.started_at).toLocaleDateString()}
                        </p>
                    )}
                    <p className="text-muted-foreground text-xs leading-relaxed">
                        {memory.summary}
                    </p>
                </div>
            </CollapsibleContent>
        </Collapsible>
    );
}
