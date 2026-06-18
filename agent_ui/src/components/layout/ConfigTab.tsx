import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { ModeSelector } from "@/components/controls/ModeSelector";
import { ModelSelector } from "@/components/controls/ModelSelector";
import { ThinkingSlider } from "@/components/controls/ThinkingSlider";
import { useMimirStore } from "@/store";
import type { LLMSettings, RagParams } from "@/types";

interface ParamRowProps {
    label: string;
    value: number | undefined;
    onChange: (v: number) => void;
    min?: number;
    max?: number;
    step?: number;
    placeholder?: string;
    disabled?: boolean;
}

function ParamRow({
    label,
    value,
    onChange,
    min,
    max,
    step,
    placeholder,
    disabled,
}: ParamRowProps) {
    return (
        <div className="flex items-center justify-between gap-3">
            <label className="text-muted-foreground min-w-0 shrink text-xs">
                {label}
            </label>
            <Input
                type="number"
                className="h-6 w-24 shrink-0 text-right font-mono text-xs"
                value={value ?? ""}
                min={min}
                max={max}
                step={step ?? 0.01}
                placeholder={placeholder}
                disabled={disabled}
                onChange={(e) => {
                    const n = parseFloat(e.target.value);
                    if (!isNaN(n)) onChange(n);
                }}
            />
        </div>
    );
}

export function ConfigTab() {
    const {
        settings,
        ragParams,
        debugMode,
        setDebugMode,
        enterToSend,
        setEnterToSend,
        setLLMParam,
        setRagParam,
        resetRagParams,
    } = useMimirStore();

    return (
        <div className="flex h-full flex-col">
            <div className="min-h-0 flex-1 overflow-hidden">
                <ScrollArea className="h-full">
                    {debugMode ? (
                        <div className="space-y-4 p-3">
                            <div className="space-y-2">
                                <p className="text-muted-foreground text-xs tracking-wide uppercase">
                                    LLM Parameters
                                </p>
                                <div className="space-y-2">
                                    <ParamRow
                                        label="Temperature"
                                        value={settings.temperature}
                                        onChange={(v) =>
                                            setLLMParam(
                                                "temperature" as keyof LLMSettings,
                                                v
                                            )
                                        }
                                        min={0}
                                        max={2}
                                        step={0.01}
                                    />
                                    <ParamRow
                                        label="Top-p"
                                        value={settings.top_p}
                                        onChange={(v) =>
                                            setLLMParam(
                                                "top_p" as keyof LLMSettings,
                                                v
                                            )
                                        }
                                        min={0}
                                        max={1}
                                        step={0.01}
                                    />
                                    <ParamRow
                                        label="Min-p"
                                        value={settings.min_p}
                                        onChange={(v) =>
                                            setLLMParam(
                                                "min_p" as keyof LLMSettings,
                                                v
                                            )
                                        }
                                        min={0}
                                        max={1}
                                        step={0.01}
                                    />
                                    <ParamRow
                                        label="Repetition penalty"
                                        value={settings.repetition_penalty}
                                        onChange={(v) =>
                                            setLLMParam(
                                                "repetition_penalty" as keyof LLMSettings,
                                                v
                                            )
                                        }
                                        min={0.5}
                                        max={2}
                                        step={0.01}
                                    />
                                    <ParamRow
                                        label="Max tokens"
                                        value={settings.max_tokens}
                                        onChange={(v) =>
                                            setLLMParam(
                                                "max_tokens" as keyof LLMSettings,
                                                Math.round(v)
                                            )
                                        }
                                        min={1}
                                        step={1}
                                    />
                                </div>
                            </div>

                            <Separator />

                            <div className="space-y-2">
                                <p className="text-muted-foreground text-xs tracking-wide uppercase">
                                    Thinking
                                </p>
                                <div className="flex items-center justify-between">
                                    <label className="text-muted-foreground text-xs">
                                        Enable thinking
                                    </label>
                                    <Switch
                                        checked={settings.enable_thinking}
                                        onCheckedChange={(v) =>
                                            setLLMParam(
                                                "enable_thinking" as keyof LLMSettings,
                                                v
                                            )
                                        }
                                    />
                                </div>
                                <ParamRow
                                    label="Thinking budget"
                                    value={
                                        settings.thinking_budget ?? undefined
                                    }
                                    onChange={(v) =>
                                        setLLMParam(
                                            "thinking_budget" as keyof LLMSettings,
                                            Math.round(v)
                                        )
                                    }
                                    min={0}
                                    step={100}
                                    disabled={!settings.enable_thinking}
                                />
                            </div>

                            <Separator />

                            <div className="space-y-2">
                                <div className="flex items-center justify-between">
                                    <p className="text-muted-foreground text-xs tracking-wide uppercase">
                                        RAG Parameters
                                    </p>
                                    <button
                                        className="text-muted-foreground hover:text-foreground text-[10px] underline-offset-2 hover:underline"
                                        onClick={resetRagParams}
                                    >
                                        reset
                                    </button>
                                </div>
                                <div className="space-y-2">
                                    <ParamRow
                                        label="Top-k"
                                        value={ragParams.top_k}
                                        onChange={(v) =>
                                            setRagParam(
                                                "top_k" as keyof RagParams,
                                                Math.round(v)
                                            )
                                        }
                                        min={1}
                                        step={1}
                                        placeholder="5"
                                    />
                                    <ParamRow
                                        label="Threshold"
                                        value={ragParams.threshold}
                                        onChange={(v) =>
                                            setRagParam(
                                                "threshold" as keyof RagParams,
                                                v
                                            )
                                        }
                                        min={0}
                                        max={1}
                                        step={0.01}
                                        placeholder="0.6"
                                    />
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-6 p-3">
                            <ModelSelector />
                            <Separator />
                            <ModeSelector />
                            <Separator />
                            <ThinkingSlider />
                            <Separator />
                            <div className="space-y-2">
                                <p className="text-muted-foreground text-xs tracking-wide uppercase">
                                    Parameters
                                </p>
                                <dl className="space-y-1">
                                    {(
                                        [
                                            [
                                                "Temperature",
                                                settings.temperature,
                                            ],
                                            ["Top-p", settings.top_p],
                                            ["Min-p", settings.min_p],
                                            ["Max tokens", settings.max_tokens],
                                        ] as [string, number][]
                                    ).map(([label, val]) => (
                                        <div
                                            key={label}
                                            className="flex justify-between text-xs"
                                        >
                                            <dt className="text-muted-foreground">
                                                {label}
                                            </dt>
                                            <dd className="text-foreground font-mono">
                                                {val}
                                            </dd>
                                        </div>
                                    ))}
                                </dl>
                            </div>
                            <Separator />
                            <div className="space-y-2">
                                <p className="text-muted-foreground text-xs tracking-wide uppercase">
                                    Input
                                </p>
                                <div className="flex items-center justify-between">
                                    <label className="text-muted-foreground text-xs">
                                        Enter sends message
                                    </label>
                                    <Switch
                                        checked={enterToSend}
                                        onCheckedChange={setEnterToSend}
                                    />
                                </div>
                            </div>
                        </div>
                    )}
                </ScrollArea>
            </div>

            <div className="border-border shrink-0 border-t p-3">
                <Button
                    variant={debugMode ? "default" : "outline"}
                    size="sm"
                    className="w-full"
                    onClick={() => setDebugMode(!debugMode)}
                >
                    {debugMode ? "Exit Debug Mode" : "Debug Mode"}
                </Button>
            </div>
        </div>
    );
}
