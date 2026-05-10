import { ScrollArea } from "@/components/ui/scroll-area";
import type { ResponseMetadata } from "@/types";
import { EpisodicMemories } from "./EpisodicMemories";
import { RagSources } from "./RagSources";
import { TokenStats } from "./TokenStats";

interface Props {
    metadata: ResponseMetadata;
}

export function MessageDetail({ metadata }: Props) {
    return (
        <ScrollArea className="h-full">
            <div className="space-y-6 p-3 pb-6">
                <TokenStats metadata={metadata} />
                <RagSources sources={metadata.rag_sources} />
                <EpisodicMemories memories={metadata.episodic_memories} />
            </div>
        </ScrollArea>
    );
}
