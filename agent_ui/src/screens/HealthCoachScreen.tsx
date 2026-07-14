import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { CaretDown } from "@phosphor-icons/react";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import type {
    HealthMetricSummary,
    HealthWeekDetail,
    HealthWeekSummary,
} from "@/types";

type MetricKey = keyof HealthMetricSummary;

interface MetricDefinition {
    key: MetricKey;
    label: string;
    unit?: string;
    decimals?: number;
}

const metricGroups: { title: string; metrics: MetricDefinition[] }[] = [
    {
        title: "Recovery",
        metrics: [
            { key: "hrv_avg", label: "HRV", unit: "ms", decimals: 0 },
            {
                key: "resting_hr_avg",
                label: "Resting HR",
                unit: "bpm",
                decimals: 0,
            },
            { key: "vo2_max", label: "VO2 max", decimals: 1 },
        ],
    },
    {
        title: "Sleep",
        metrics: [
            { key: "sleep_total_h", label: "Total", unit: "h", decimals: 1 },
            { key: "sleep_deep_h", label: "Deep", unit: "h", decimals: 1 },
            { key: "sleep_rem_h", label: "REM", unit: "h", decimals: 1 },
            {
                key: "sleep_efficiency_pct",
                label: "Efficiency",
                unit: "%",
                decimals: 0,
            },
        ],
    },
    {
        title: "Training",
        metrics: [
            { key: "steps_avg", label: "Steps", decimals: 0 },
            { key: "active_kcal_avg", label: "Active kcal", decimals: 0 },
            {
                key: "exercise_min_avg",
                label: "Exercise",
                unit: "min",
                decimals: 0,
            },
            {
                key: "total_distance_km",
                label: "Distance",
                unit: "km",
                decimals: 1,
            },
        ],
    },
    {
        title: "Body",
        metrics: [
            { key: "avg_tdee", label: "TDEE", decimals: 0 },
            { key: "weight_kg_avg", label: "Weight", unit: "kg", decimals: 1 },
            {
                key: "body_fat_pct_avg",
                label: "Body fat",
                unit: "%",
                decimals: 1,
            },
        ],
    },
];

function formatWeek(week: HealthWeekSummary): string {
    return `${week.week_start} - ${week.week_end}`;
}

function formatMetric(
    value: number | null,
    unit?: string,
    decimals = 1
): string {
    if (value === null) return "-";
    const formatted = new Intl.NumberFormat(undefined, {
        maximumFractionDigits: decimals,
        minimumFractionDigits: decimals > 0 ? 0 : 0,
    }).format(value);
    return unit ? `${formatted} ${unit}` : formatted;
}

async function fetchHealthWeek(weekStart: string): Promise<HealthWeekDetail> {
    const res = await fetch(`/api/health/weeks/${weekStart}`);
    if (!res.ok) throw new Error("Failed to load health week");
    return res.json() as Promise<HealthWeekDetail>;
}

export function HealthCoachScreen() {
    const [latest, setLatest] = useState<HealthWeekDetail | null>(null);
    const [history, setHistory] = useState<HealthWeekSummary[]>([]);
    const [loadedDetails, setLoadedDetails] = useState<
        Record<string, HealthWeekDetail>
    >({});
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.all([
            fetch("/api/health/latest").then((r) => {
                if (r.status === 404) return null;
                if (!r.ok) throw new Error("Failed to load latest health week");
                return r.json() as Promise<HealthWeekDetail>;
            }),
            fetch("/api/health/weeks").then((r) => {
                if (!r.ok) throw new Error("Failed to load health history");
                return r.json() as Promise<HealthWeekSummary[]>;
            }),
        ])
            .then(([latestWeek, weeks]) => {
                setLatest(latestWeek);
                const pastWeeks = latestWeek
                    ? weeks.filter(
                          (w) => w.week_start !== latestWeek.week_start
                      )
                    : weeks;
                setHistory(pastWeeks);
            })
            .catch(() => toast.error("Failed to load health coach"))
            .finally(() => setLoading(false));
    }, []);

    async function handleExpand(summary: HealthWeekSummary) {
        if (loadedDetails[summary.week_start]) return;
        try {
            const detail = await fetchHealthWeek(summary.week_start);
            setLoadedDetails((prev) => ({
                ...prev,
                [summary.week_start]: detail,
            }));
        } catch {
            toast.error("Failed to load health week");
        }
    }

    return (
        <div className="flex h-full flex-col overflow-hidden">
            <div className="border-border shrink-0 border-b px-6 py-4">
                <h1 className="font-heading text-xl font-semibold tracking-tight">
                    Health Coach
                </h1>
                {latest && (
                    <p className="text-muted-foreground mt-1 text-xs">
                        {formatWeek(latest)}
                    </p>
                )}
            </div>

            <ScrollArea className="min-h-0 flex-1">
                <div className="mx-auto max-w-4xl px-6 py-6">
                    {loading ? (
                        <LoadingState />
                    ) : !latest ? (
                        <p className="text-muted-foreground pt-8 text-center text-sm">
                            No health coach results yet — weekly analysis
                            appears here after the next workflow run.
                        </p>
                    ) : (
                        <>
                            <MetricGrid metrics={latest.metrics} />
                            <AnalysisBlock detail={latest} />

                            {history.length > 0 && (
                                <>
                                    <Separator className="my-6" />
                                    <h2 className="mb-3 text-sm font-semibold">
                                        Past Weeks
                                    </h2>
                                    <div className="space-y-2">
                                        {history.map((summary) => (
                                            <Collapsible
                                                key={summary.week_start}
                                                onOpenChange={(open) => {
                                                    if (open)
                                                        handleExpand(summary);
                                                }}
                                            >
                                                <CollapsibleTrigger className="bg-card border-border hover:bg-muted/30 flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-sm transition-colors">
                                                    <span className="text-foreground">
                                                        {formatWeek(summary)}
                                                    </span>
                                                    <span className="ml-auto flex items-center gap-2">
                                                        {!summary.has_analysis && (
                                                            <span className="text-muted-foreground text-xs">
                                                                analysis pending
                                                            </span>
                                                        )}
                                                        <CaretDown className="text-muted-foreground h-4 w-4 shrink-0" />
                                                    </span>
                                                </CollapsibleTrigger>
                                                <CollapsibleContent>
                                                    <div className="border-border bg-card/40 mt-1 rounded-lg border px-4 py-4">
                                                        {loadedDetails[
                                                            summary.week_start
                                                        ] ? (
                                                            <>
                                                                <MetricGrid
                                                                    metrics={
                                                                        loadedDetails[
                                                                            summary
                                                                                .week_start
                                                                        ]
                                                                            .metrics
                                                                    }
                                                                    compact
                                                                />
                                                                <AnalysisBlock
                                                                    detail={
                                                                        loadedDetails[
                                                                            summary
                                                                                .week_start
                                                                        ]
                                                                    }
                                                                />
                                                            </>
                                                        ) : (
                                                            <div className="space-y-2">
                                                                {[1, 2, 3].map(
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

function LoadingState() {
    return (
        <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                {[1, 2, 3, 4].map((i) => (
                    <Skeleton key={i} className="h-28 w-full rounded-lg" />
                ))}
            </div>
            {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-5 w-full rounded" />
            ))}
        </div>
    );
}

function MetricGrid({
    metrics,
    compact = false,
}: {
    metrics: HealthMetricSummary;
    compact?: boolean;
}) {
    return (
        <div
            className={
                compact
                    ? "mb-4 grid grid-cols-1 gap-3 lg:grid-cols-2"
                    : "mb-6 grid grid-cols-1 gap-3 lg:grid-cols-2"
            }
        >
            {metricGroups.map((group) => (
                <Card
                    key={group.title}
                    className="bg-card/60 border-border p-4"
                >
                    <h3 className="mb-3 text-xs font-semibold tracking-wide uppercase">
                        {group.title}
                    </h3>
                    <div className="grid grid-cols-2 gap-3">
                        {group.metrics.map((metric) => (
                            <div key={metric.key} className="min-w-0">
                                <p className="text-muted-foreground truncate text-xs">
                                    {metric.label}
                                </p>
                                <p className="text-sm font-medium">
                                    {formatMetric(
                                        metrics[metric.key],
                                        metric.unit,
                                        metric.decimals
                                    )}
                                </p>
                            </div>
                        ))}
                    </div>
                </Card>
            ))}
        </div>
    );
}

function AnalysisBlock({ detail }: { detail: HealthWeekDetail }) {
    if (!detail.analysis_md) {
        return (
            <p className="text-muted-foreground py-4 text-sm">
                Analysis is not available for this week yet.
            </p>
        );
    }

    return (
        <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown>{detail.analysis_md}</ReactMarkdown>
        </div>
    );
}
