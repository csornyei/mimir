import { useState } from "react";
import { CaretDown } from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";
import type { RagSource } from "@/types";

interface Props {
    sources: RagSource[];
}

const TYPE_CLASSES: Record<RagSource["source_type"], string> = {
    markdown: "bg-blue-950/50 text-blue-300 border-blue-800/50",
    pdf: "bg-orange-950/50 text-orange-300 border-orange-800/50",
    kiwix: "bg-purple-950/50 text-purple-300 border-purple-800/50",
    wallabag: "bg-green-950/50 text-green-300 border-green-800/50",
};

export function RagSources({ sources }: Props) {
    if (sources.length === 0) return null;

    return (
        <div className="space-y-2">
            <p className="text-muted-foreground text-xs tracking-wide uppercase">
                RAG Sources ({sources.length})
            </p>
            {sources.map((src) => (
                <RagSourceCard
                    key={`${src.source_path}:${src.chunk_index}`}
                    source={src}
                />
            ))}
        </div>
    );
}

function RagSourceCard({ source }: { source: RagSource }) {
    const [open, setOpen] = useState(false);
    const filename = source.source_path.split("/").pop() ?? source.source_path;

    return (
        <Card className="bg-card/60 border-border overflow-hidden text-xs">
            <Collapsible open={open} onOpenChange={setOpen}>
                <CollapsibleTrigger className="hover:bg-muted/30 flex w-full items-center gap-2 px-3 py-2 text-left transition-colors">
                    <Badge
                        className={`shrink-0 border text-[10px] ${TYPE_CLASSES[source.source_type]}`}
                    >
                        {source.source_type}
                    </Badge>
                    <span className="text-foreground min-w-0 flex-1 truncate font-mono">
                        {filename}
                    </span>
                    <span className="text-muted-foreground shrink-0">
                        {(source.similarity_score * 100).toFixed(0)}%
                    </span>
                    <CaretDown
                        className={`text-muted-foreground h-3 w-3 shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
                    />
                </CollapsibleTrigger>
                <CollapsibleContent>
                    <div className="border-border space-y-1 border-t px-3 pt-1 pb-3">
                        <p className="text-muted-foreground font-mono text-[10px]">
                            {source.source_path}
                        </p>
                        <p className="text-muted-foreground leading-relaxed">
                            {source.content_preview}
                        </p>
                    </div>
                </CollapsibleContent>
            </Collapsible>
        </Card>
    );
}
