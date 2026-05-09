import { Slider } from '@/components/ui/slider'
import { useMimirStore } from '@/store'
import type { LLMSettings } from '@/types'

const STOPS: { label: string; budget: number | null; enabled: boolean }[] = [
  { label: 'None', budget: 0, enabled: false },
  { label: 'Small', budget: 2000, enabled: true },
  { label: 'Large', budget: 8000, enabled: true },
  { label: 'Unlimited', budget: null, enabled: true },
]

function settingsToIndex(s: Pick<LLMSettings, 'enable_thinking' | 'thinking_budget'>): number {
  if (!s.enable_thinking) return 0
  if (s.thinking_budget === null) return 3
  if (s.thinking_budget <= 2000) return 1
  return 2
}

export function ThinkingSlider() {
  const { settings, setThinkingBudget, setEnableThinking } = useMimirStore()
  const idx = settingsToIndex(settings)

  function handleChange([i]: number[]) {
    const stop = STOPS[i]
    setEnableThinking(stop.enabled)
    setThinkingBudget(stop.budget)
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground uppercase tracking-wide">Thinking budget</p>
        <span className="text-xs font-mono text-foreground">{STOPS[idx].label}</span>
      </div>
      <Slider min={0} max={3} step={1} value={[idx]} onValueChange={handleChange} />
      <div className="flex justify-between">
        {STOPS.map(({ label }, i) => (
          <span key={i} className="text-[10px] text-muted-foreground/60">
            {label}
          </span>
        ))}
      </div>
    </div>
  )
}
