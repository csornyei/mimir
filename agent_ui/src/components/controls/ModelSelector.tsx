import { useMimirStore } from "@/store";

function formatSize(bytes: number | null): string {
    if (bytes == null) return "";
    const gb = bytes / 1e9;
    return gb >= 1 ? `${gb.toFixed(1)}GB` : `${(bytes / 1e6).toFixed(0)}MB`;
}

export function ModelSelector() {
    const { settings, models, setModel } = useMimirStore();

    return (
        <div className="space-y-2">
            <p className="text-muted-foreground text-xs tracking-wide uppercase">
                Model
            </p>
            {models.length === 0 ? (
                <div className="text-foreground/80 text-sm">
                    No models available
                </div>
            ) : (
                <select
                    value={settings.model ?? ""}
                    onChange={(e) => setModel(e.target.value || undefined)}
                    className="border-input bg-background text-foreground w-full rounded-md border px-2 py-1.5 text-xs focus:outline-none"
                >
                    <option value="">Default</option>
                    {models.map((m) => (
                        <option key={m.name} value={m.name}>
                            {m.is_loaded ? "⚡ " : ""}
                            {m.name}
                            {m.size ? ` · ${formatSize(m.size)}` : ""}
                        </option>
                    ))}
                </select>
            )}
        </div>
    );
}
