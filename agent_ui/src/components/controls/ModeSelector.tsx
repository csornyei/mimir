import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useMimirStore } from "@/store";
import type { Mode } from "@/lib/presets";

const MODES: { value: Mode; label: string; hint: string }[] = [
    { value: "precise", label: "Precise", hint: "Low temp · 2k thinking" },
    { value: "balanced", label: "Balanced", hint: "Mid temp · 2k thinking" },
    { value: "creative", label: "Creative", hint: "High temp · 8k thinking" },
    { value: "fast", label: "Fast", hint: "No thinking" },
];

export function ModeSelector() {
    const { settings, setMode } = useMimirStore();

    return (
        <div className="space-y-2">
            <p className="text-muted-foreground text-xs tracking-wide uppercase">
                Mode
            </p>
            <ToggleGroup
                type="single"
                value={settings.mode}
                onValueChange={(v) => {
                    if (v) setMode(v as Mode);
                }}
                className="grid w-full grid-cols-2 gap-1"
            >
                {MODES.map(({ value, label }) => (
                    <ToggleGroupItem
                        key={value}
                        value={value}
                        className="w-full text-xs"
                    >
                        {label}
                    </ToggleGroupItem>
                ))}
            </ToggleGroup>
            <p className="text-muted-foreground/60 text-[10px]">
                {MODES.find((m) => m.value === settings.mode)?.hint}
            </p>
        </div>
    );
}
