import { useEffect, useState } from "react";
import { CaretDown } from "@phosphor-icons/react";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import type { BriefDetail, BriefSummary } from "@/types";

export function BriefScreen() {
    const [latest, setLatest] = useState<BriefDetail | null>(null);
    const [history, setHistory] = useState<BriefSummary[]>([]);
    const [loadedDetails, setLoadedDetails] = useState<
        Record<string, BriefDetail>
    >({});
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.all([
            fetch("/api/brief/latest").then((r) => {
                if (r.status === 404) return null;
                if (!r.ok) throw new Error("Failed to load latest brief");
                return r.json() as Promise<BriefDetail>;
            }),
            fetch("/api/brief").then((r) => {
                if (!r.ok) throw new Error("Failed to load brief history");
                return r.json() as Promise<BriefSummary[]>;
            }),
        ])
            .then(([latestBrief, briefs]) => {
                setLatest(latestBrief);
                const pastBriefs = latestBrief
                    ? briefs.filter((b) => b.id !== latestBrief.id)
                    : briefs;
                setHistory(pastBriefs);
            })
            .catch(() => toast.error("Failed to load morning brief"))
            .finally(() => setLoading(false));
    }, []);

    async function handleExpand(summary: BriefSummary) {
        if (loadedDetails[summary.id]) return;
        try {
            const res = await fetch(`/api/brief/${summary.date}`);
            if (!res.ok) throw new Error();
            const detail = (await res.json()) as BriefDetail;
            setLoadedDetails((prev) => ({ ...prev, [summary.id]: detail }));
        } catch {
            toast.error("Failed to load brief");
        }
    }

    const assistantContent = latest?.messages.find(
        (m) => m.role === "assistant"
    )?.content;

    return (
        <div className="flex h-full flex-col overflow-hidden">
            <div className="border-border shrink-0 border-b px-6 py-4">
                <h1 className="text-base font-semibold">Morning Brief</h1>
                {latest && (
                    <p className="text-muted-foreground mt-1 text-xs">
                        {latest.date}
                    </p>
                )}
            </div>

            <ScrollArea className="min-h-0 flex-1">
                <div className="mx-auto max-w-3xl px-6 py-6">
                    {loading ? (
                        <div className="space-y-3">
                            {[1, 2, 3, 4].map((i) => (
                                <Skeleton
                                    key={i}
                                    className="h-5 w-full rounded"
                                />
                            ))}
                        </div>
                    ) : !latest ? (
                        <p className="text-muted-foreground pt-8 text-center text-sm">
                            No morning brief yet.
                        </p>
                    ) : (
                        <>
                            <div className="prose prose-sm dark:prose-invert max-w-none">
                                <ReactMarkdown>
                                    {assistantContent ?? ""}
                                </ReactMarkdown>
                            </div>

                            {history.length > 0 && (
                                <>
                                    <Separator className="my-6" />
                                    <h2 className="mb-3 text-sm font-semibold">
                                        Past Briefs
                                    </h2>
                                    <div className="space-y-2">
                                        {history.map((summary) => (
                                            <Collapsible
                                                key={summary.id}
                                                onOpenChange={(open) => {
                                                    if (open)
                                                        handleExpand(summary);
                                                }}
                                            >
                                                <CollapsibleTrigger className="bg-card border-border hover:bg-muted/30 flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-sm transition-colors">
                                                    <span className="text-foreground">
                                                        {summary.date}
                                                    </span>
                                                    <CaretDown className="text-muted-foreground ml-auto h-4 w-4 shrink-0" />
                                                </CollapsibleTrigger>
                                                <CollapsibleContent>
                                                    <div className="border-border bg-card/40 mt-1 rounded-lg border px-4 py-3">
                                                        {loadedDetails[
                                                            summary.id
                                                        ] ? (
                                                            <div className="prose prose-sm dark:prose-invert max-w-none">
                                                                <ReactMarkdown>
                                                                    {loadedDetails[
                                                                        summary
                                                                            .id
                                                                    ].messages.find(
                                                                        (m) =>
                                                                            m.role ===
                                                                            "assistant"
                                                                    )
                                                                        ?.content ??
                                                                        ""}
                                                                </ReactMarkdown>
                                                            </div>
                                                        ) : (
                                                            <div className="space-y-2">
                                                                {[1, 2].map(
                                                                    (i) => (
                                                                        <Skeleton
                                                                            key={
                                                                                i
                                                                            }
                                                                            className="h-4 w-full rounded"
                                                                        />
                                                                    )
                                                                )}
                                                            </div>
                                                        )}
                                                    </div>
                                                </CollapsibleContent>
                                            </Collapsible>
                                        ))}
                                    </div>
                                </>
                            )}
                        </>
                    )}
                </div>
            </ScrollArea>
        </div>
    );
}
