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

interface DigestArticle {
    id: number;
    title: string;
    url: string;
    feed_name: string | null;
    category: string | null;
    window: string;
    digest_run_at: string;
}

type Ratings = Record<number, "up" | "down">;

function groupByRun(articles: DigestArticle[]): [string, DigestArticle[]][] {
    const map = new Map<string, DigestArticle[]>();
    for (const a of articles) {
        const existing = map.get(a.digest_run_at) ?? [];
        existing.push(a);
        map.set(a.digest_run_at, existing);
    }
    return Array.from(map.entries());
}

export function DigestScreen() {
    const [latest, setLatest] = useState<DigestArticle[]>([]);
    const [pastGroups, setPastGroups] = useState<[string, DigestArticle[]][]>(
        []
    );
    const [ratings, setRatings] = useState<Ratings>({});
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.all([
            fetch("/api/digest/latest").then(
                (r) => r.json() as Promise<DigestArticle[]>
            ),
            fetch("/api/digest/history?limit=100").then(
                (r) => r.json() as Promise<DigestArticle[]>
            ),
        ])
            .then(([latestArticles, historyArticles]) => {
                setLatest(latestArticles);
                const latestRunAt = latestArticles[0]?.digest_run_at;
                const olderArticles = historyArticles.filter(
                    (a) => a.digest_run_at !== latestRunAt
                );
                setPastGroups(groupByRun(olderArticles));
                // TODO: persist ratings via localStorage
            })
            .catch(() => toast.error("Failed to load digest"))
            .finally(() => setLoading(false));
    }, []);

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

    const latestMeta = latest[0];

    return (
        <div className="flex h-full flex-col overflow-hidden">
            <div className="border-border shrink-0 border-b px-6 py-4">
                <h1 className="text-base font-semibold">RSS Digest</h1>
                {latestMeta && (
                    <p className="text-muted-foreground mt-1 text-xs">
                        {latestMeta.window} ·{" "}
                        {new Date(latestMeta.digest_run_at).toLocaleString()}
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
                    ) : latest.length > 0 ? (
                        <>
                            <div className="mb-8 space-y-3">
                                {latest.map((article) => (
                                    <ArticleCard
                                        key={article.id}
                                        article={article}
                                        rating={ratings[article.id]}
                                        onFeedback={handleFeedback}
                                    />
                                ))}
                            </div>

                            {pastGroups.length > 0 && (
                                <>
                                    <Separator className="my-4" />
                                    <h2 className="mb-3 text-sm font-semibold">
                                        Past Digests
                                    </h2>
                                    <div className="space-y-2">
                                        {pastGroups.map(([runAt, articles]) => (
                                            <Collapsible key={runAt}>
                                                <CollapsibleTrigger className="bg-card border-border hover:bg-muted/30 flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-sm transition-colors">
                                                    <span className="text-foreground">
                                                        {new Date(
                                                            runAt
                                                        ).toLocaleDateString()}
                                                    </span>
                                                    <span className="text-muted-foreground text-xs">
                                                        {articles[0]?.window}
                                                    </span>
                                                    <span className="text-muted-foreground ml-auto text-xs">
                                                        {articles.length}{" "}
                                                        articles
                                                    </span>
                                                    <CaretDown className="text-muted-foreground h-4 w-4 shrink-0" />
                                                </CollapsibleTrigger>
                                                <CollapsibleContent>
                                                    <div className="space-y-2 pt-2 pb-1">
                                                        {articles.map(
                                                            (article) => (
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
                                                            )
                                                        )}
                                                    </div>
                                                </CollapsibleContent>
                                            </Collapsible>
                                        ))}
                                    </div>
                                </>
                            )}
                        </>
                    ) : (
                        <p className="text-muted-foreground pt-8 text-center text-sm">
                            No digest yet.
                        </p>
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
