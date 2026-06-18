import { useTheme } from "next-themes";
import { Moon, Sun } from "@phosphor-icons/react";

export function ThemeToggle() {
    const { resolvedTheme, setTheme } = useTheme();
    // Defaults to dark until next-themes resolves (matches defaultTheme).
    const isDark = resolvedTheme !== "light";

    return (
        <button
            className="text-muted-foreground hover:text-foreground hover:bg-accent flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors"
            onClick={() => setTheme(isDark ? "light" : "dark")}
            aria-label={
                isDark ? "Switch to light theme" : "Switch to dark theme"
            }
        >
            {isDark ? (
                <Sun className="h-4 w-4" />
            ) : (
                <Moon className="h-4 w-4" />
            )}
            {isDark ? "Light theme" : "Dark theme"}
        </button>
    );
}
