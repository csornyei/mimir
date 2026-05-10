import { useState } from "react";
import { CaretDown, Wrench } from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";
import type { ToolCall } from "@/types";

interface Props {
    toolCall: ToolCall;
}

export function ToolCallCard({ toolCall }: Props) {
    const [open, setOpen] = useState(false);

    const firstArg = Object.entries(toolCall.arguments)[0];
    const preview = firstArg
        ? `${firstArg[0]}: ${JSON.stringify(firstArg[1]).slice(0, 40)}`
        : "";

    return (
        <Card className="bg-card/60 border-border overflow-hidden text-xs">
            <Collapsible open={open} onOpenChange={setOpen}>
                <CollapsibleTrigger className="hover:bg-muted/30 flex w-full items-center gap-2 px-3 py-2 text-left transition-colors">
                    <Wrench className="text-muted-foreground h-3 w-3 shrink-0" />
                    <span className="text-foreground font-mono">
                        {toolCall.name}
                    </span>
                    {preview && (
                        <span className="text-muted-foreground min-w-0 flex-1 truncate">
                            {preview}
                        </span>
                    )}
                    {toolCall.result === null ? (
                        <Badge
                            variant="outline"
                            className="border-border ml-auto shrink-0 text-[10px]"
                        >
                            running
                        </Badge>
                    ) : (
                        <Badge
                            variant="outline"
                            className="border-border ml-auto shrink-0 text-[10px] text-green-500"
                        >
                            done
                        </Badge>
                    )}
                    <CaretDown
                        className={`text-muted-foreground h-3 w-3 shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
                    />
                </CollapsibleTrigger>
                <CollapsibleContent>
                    <div className="border-border space-y-2 border-t px-3 pt-2 pb-3">
                        <div>
                            <p className="text-muted-foreground mb-1 text-[10px] tracking-wide uppercase">
                                Arguments
                            </p>
                            <pre className="text-muted-foreground font-mono leading-relaxed break-all whitespace-pre-wrap">
                                {JSON.stringify(toolCall.arguments, null, 2)}
                            </pre>
                        </div>
                        {toolCall.result !== null && (
                            <div>
                                <p className="text-muted-foreground mb-1 text-[10px] tracking-wide uppercase">
                                    Result
                                </p>
                                <pre className="text-muted-foreground max-h-40 overflow-auto font-mono leading-relaxed break-all whitespace-pre-wrap">
                                    {toolCall.result}
                                </pre>
                            </div>
                        )}
                    </div>
                </CollapsibleContent>
            </Collapsible>
        </Card>
    );
}
