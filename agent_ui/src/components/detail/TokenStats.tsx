import type { ResponseMetadata } from "@/types";

interface Props {
    metadata: ResponseMetadata;
}

export function TokenStats({ metadata }: Props) {
    const total =
        metadata.thinking_tokens +
        metadata.response_tokens +
        metadata.prompt_tokens;

    return (
        <div className="space-y-2">
            <p className="text-muted-foreground text-xs tracking-wide uppercase">
                Tokens &amp; Latency
            </p>
            <div className="grid grid-cols-2 gap-2">
                {(
                    [
                        ["Prompt", metadata.prompt_tokens],
                        ["Thinking", metadata.thinking_tokens],
                        ["Response", metadata.response_tokens],
                        ["Total", total],
                    ] as [string, number][]
                ).map(([label, value]) => (
                    <div
                        key={label}
                        className="bg-muted/30 border-border rounded-lg border px-3 py-2"
                    >
                        <p className="text-muted-foreground text-[10px] uppercase">
                            {label}
                        </p>
                        <p className="text-foreground mt-0.5 font-mono text-xs">
                            {value.toLocaleString()}
                        </p>
                    </div>
                ))}
            </div>
            <div className="bg-muted/30 border-border flex items-center justify-between rounded-lg border px-3 py-2">
                <span className="text-muted-foreground text-xs">Latency</span>
                <span className="text-foreground font-mono text-xs">
                    {metadata.latency_ms.toLocaleString()} ms
                </span>
            </div>
        </div>
    );
}
