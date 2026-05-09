import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { useMimirStore } from '@/store'
import type { Mode } from '@/lib/presets'

const MODES: { value: Mode; label: string; hint: string }[] = [
  { value: 'precise', label: 'Precise', hint: 'Low temp · 2k thinking' },
  { value: 'balanced', label: 'Balanced', hint: 'Mid temp · 2k thinking' },
  { value: 'creative', label: 'Creative', hint: 'High temp · 8k thinking' },
  { value: 'fast', label: 'Fast', hint: 'No thinking' },
]

export function ModeSelector() {
  const { settings, setMode } = useMimirStore()

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground uppercase tracking-wide">Mode</p>
      <ToggleGroup
        type="single"
        value={settings.mode}
        onValueChange={(v) => {
          if (v) setMode(v as Mode)
        }}
        className="grid grid-cols-2 gap-1 w-full"
      >
        {MODES.map(({ value, label }) => (
          <ToggleGroupItem key={value} value={value} className="text-xs w-full">
            {label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      <p className="text-[10px] text-muted-foreground/60">
        {MODES.find((m) => m.value === settings.mode)?.hint}
      </p>
    </div>
  )
}
