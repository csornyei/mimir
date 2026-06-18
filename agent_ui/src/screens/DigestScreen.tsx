import { useEffect, useState } from "react";
import { ThumbsDown, ThumbsUp, CaretDown } from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import type { DigestArticle, DigestRun } from "@/types";

type Ratings = Record<number, "up" | "down">;

function formatRunLabel(run: DigestRun): string {
    const date = new Date(run.run_at).toISOString().slice(0, 10);
    return `${date}: ${run.window}`;
}

export function DigestScreen() {
    const [runs, setRuns] = useState<DigestRun[]>([]);
    const [articlesByRun, setArticlesByRun] = useState<
        Record<string, DigestArticle[]>
    >({});
    const [ratings, setRatings] = useState<Ratings>({});
    const [loading, setLoading] = useState(true);

    async function fetchRunArticles(runAt: string): Promise<DigestArticle[]> {
        const res = await fetch(
            `/api/digest/run?run_at=${encodeURIComponent(runAt)}`
        );
        if (!res.ok) throw new Error("Failed to load run");
        return res.json() as Promise<DigestArticle[]>;
    }

    useEffect(() => {
        fetch("/api/digest/runs")
            .then((r) => r.json() as Promise<DigestRun[]>)
            .then(async (fetchedRuns) => {
                setRuns(fetchedRuns);
                if (fetchedRuns.length > 0) {
                    const latest = fetchedRuns[0];
                    const articles = await fetchRunArticles(latest.run_at);
                    setArticlesByRun({ [latest.run_at]: articles });
                }
            })
            .catch(() => toast.error("Failed to load digest"))
            .finally(() => setLoading(false));
    }, []);

    async function handleExpand(run: DigestRun) {
        if (articlesByRun[run.run_at]) return;
        try {
            const articles = await fetchRunArticles(run.run_at);
            setArticlesByRun((prev) => ({ ...prev, [run.run_at]: articles }));
        } catch {
            toast.error("Failed to load digest run");
        }
    }

    async function handleFeedback(articleId: number, rating: "up" | "down") {
        setRatings((r) => ({ ...r, [articleId]: rating }));
        try {
            const res = await fetch("/api/digest/feedback", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ article_id: articleId, rating }),
            });
            if (!res.ok) throw new Error();
        } catch {
            toast.error("Failed to submit feedback");
            setRatings((r) => {
                const next = { ...r };
                delete next[articleId];
                return next;
            });
        }
    }

    const latestRun = runs[0];
    const pastRuns = runs.slice(1);

    return (
        <div className="flex h-full flex-col overflow-hidden">
            <div className="border-border shrink-0 border-b px-6 py-4">
                <h1 className="font-heading text-xl font-semibold tracking-tight">
                    RSS Digest
                </h1>
                {latestRun && (
                    <p className="text-muted-foreground mt-1 text-xs">
                        {formatRunLabel(latestRun)} · {latestRun.article_count}{" "}
                        articles
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
                                    className="h-24 w-full rounded-lg"
                                />
                            ))}
                        </div>
                    ) : !latestRun ? (
                        <p className="text-muted-foreground pt-8 text-center text-sm">
                            No digest yet — articles from your RSS feeds gather
                            here after the next run.
                        </p>
                    ) : (
                        <>
                            <div className="mb-8 space-y-3">
                                {(articlesByRun[latestRun.run_at] ?? []).map(
                                    (article) => (
                                        <ArticleCard
                                            key={article.id}
                                            article={article}
                                            rating={ratings[article.id]}
                                            onFeedback={handleFeedback}
                                        />
                                    )
                                )}
                            </div>

                            {pastRuns.length > 0 && (
                                <>
                                    <Separator className="my-4" />
                                    <h2 className="mb-3 text-sm font-semibold">
                                        Past Digests
                                    </h2>
                                    <div className="space-y-2">
                                        {pastRuns.map((run) => (
                                            <Collapsible
                                                key={run.run_at}
                                                onOpenChange={(open) => {
                                                    if (open) handleExpand(run);
                                                }}
                                            >
                                                <CollapsibleTrigger className="bg-card border-border hover:bg-muted/30 flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-sm transition-colors">
                                                    <span className="text-foreground">
                                                        {formatRunLabel(run)}
                                                    </span>
                                                    <span className="text-muted-foreground ml-auto text-xs">
                                                        {run.article_count}{" "}
                                                        articles
                                                    </span>
                                                    <CaretDown className="text-muted-foreground h-4 w-4 shrink-0" />
                                                </CollapsibleTrigger>
                                                <CollapsibleContent>
                                                    <div className="space-y-2 pt-2 pb-1">
                                                        {articlesByRun[
                                                            run.run_at
                                                        ] ? (
                                                            articlesByRun[
                                                                run.run_at
                                                            ].map((article) => (
                                                                <ArticleCard
                                                                    key={
                                                                        article.id
                                                                    }
                                                                    article={
                                                                        article
                                                                    }
                                                                    rating={
                                                                        ratings[
                                                                            article
                                                                                .id
                                                                        ]
                                                                    }
                                                                    onFeedback={
                                                                        handleFeedback
                                                                    }
                                                                />
                                                            ))
                                                        ) : (
                                                            <Skeleton className="h-20 w-full rounded-lg" />
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

interface ArticleCardProps {
    article: DigestArticle;
    rating: "up" | "down" | undefined;
    onFeedback: (id: number, rating: "up" | "down") => void;
}

function ArticleCard({ article, rating, onFeedback }: ArticleCardProps) {
    return (
        <Card className="bg-card/60 border-border p-4">
            <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                    <div className="mb-1.5 flex flex-wrap items-center gap-2">
                        {article.feed_name && (
                            <Badge
                                variant="outline"
                                className="border-border text-muted-foreground shrink-0 text-[10px]"
                            >
                                {article.feed_name}
                            </Badge>
                        )}
                        {article.category && (
                            <Badge
                                variant="outline"
                                className="border-border text-muted-foreground shrink-0 text-[10px]"
                            >
                                {article.category}
                            </Badge>
                        )}
                    </div>
                    <a
                        href={article.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-foreground line-clamp-2 text-sm leading-snug font-medium hover:underline"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {article.title}
                    </a>
                </div>
                <div className="flex shrink-0 flex-col gap-1">
                    <Button
                        size="icon"
                        variant={rating === "up" ? "default" : "outline"}
                        className="h-8 w-8"
                        onClick={() => onFeedback(article.id, "up")}
                        aria-label="Thumbs up"
                    >
                        <ThumbsUp className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                        size="icon"
                        variant={rating === "down" ? "destructive" : "outline"}
                        className="h-8 w-8"
                        onClick={() => onFeedback(article.id, "down")}
                        aria-label="Thumbs down"
                    >
                        <ThumbsDown className="h-3.5 w-3.5" />
                    </Button>
                </div>
            </div>
        </Card>
    );
}
