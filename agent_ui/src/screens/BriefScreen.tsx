import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";

interface BriefEntry {
    id: string;
    content: string;
    generated_at: string;
}

export function BriefScreen() {
    const [latest, setLatest] = useState<BriefEntry | null>(null);
    const [loading, setLoading] = useState(true);
    const [unavailable, setUnavailable] = useState(false);

    useEffect(() => {
        fetch("/api/brief")
            .then(async (r) => {
                if (r.status === 501) {
                    setUnavailable(true);
                    return;
                }
                if (!r.ok) throw new Error("Failed to load brief");
                const d: BriefEntry = await r.json();
                setLatest(d);
            })
            .catch(() => toast.error("Failed to load morning brief"))
            .finally(() => setLoading(false));
    }, []);

    return (
        <div className="flex h-full flex-col overflow-hidden">
            <div className="border-border shrink-0 border-b px-6 py-4">
                <h1 className="text-base font-semibold">Morning Brief</h1>
                {latest?.generated_at && (
                    <p className="text-muted-foreground mt-1 text-xs">
                        {new Date(latest.generated_at).toLocaleString()}
                    </p>
                )}
            </div>

            <ScrollArea className="min-h-0 flex-1">
                <div className="mx-auto max-w-3xl px-6 py-4">
                    {loading ? (
                        <div className="space-y-3">
                            {[1, 2, 3].map((i) => (
                                <Skeleton
                                    key={i}
                                    className="h-4"
                                    style={{ width: `${65 + i * 8}%` }}
                                />
                            ))}
                        </div>
                    ) : unavailable ? (
                        <Alert className="border-border">
                            <AlertDescription className="text-muted-foreground text-sm">
                                Morning briefs are generated via Slack and are
                                not available in the web UI.
                            </AlertDescription>
                        </Alert>
                    ) : latest ? (
                        <div className="prose prose-sm prose-invert max-w-none">
                            <ReactMarkdown>{latest.content}</ReactMarkdown>
                            {/* TODO: wire up history from /api/brief/history */}
                        </div>
                    ) : (
                        <p className="text-muted-foreground pt-8 text-center text-sm">
                            No morning brief yet.
                        </p>
                    )}
                </div>
            </ScrollArea>
        </div>
    );
}
