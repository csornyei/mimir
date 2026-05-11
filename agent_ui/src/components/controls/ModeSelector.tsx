import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useMimirStore } from "@/store";
import type { Mode } from "@/store";

export function ModeSelector() {
    const { settings, setMode, presets } = useMimirStore();

    const activePreset = presets.find((p) => p.name === settings.mode);
    const hint = activePreset
        ? `${activePreset.temperature} temp · ${
              activePreset.enable_thinking
                  ? `${activePreset.thinking_budget ?? "∞"}t thinking`
                  : "no thinking"
          }`
        : undefined;

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
                {presets.map(({ name, label }) => (
                    <ToggleGroupItem
                        key={name}
                        value={name}
                        className="w-full text-xs"
                    >
                        {label}
                    </ToggleGroupItem>
                ))}
            </ToggleGroup>
            {hint && (
                <p className="text-muted-foreground/60 text-[10px]">{hint}</p>
            )}
        </div>
    );
}
