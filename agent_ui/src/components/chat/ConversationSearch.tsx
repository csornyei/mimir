import { MagnifyingGlass } from "@phosphor-icons/react";

interface Props {
    onClick: () => void;
}

export function ConversationSearch({ onClick }: Props) {
    return (
        <button
            onClick={onClick}
            className="text-muted-foreground border-border bg-background hover:bg-accent hover:text-foreground flex w-full items-center gap-2 rounded-md border px-2 py-1.5 text-xs transition-colors"
        >
            <MagnifyingGlass className="h-3.5 w-3.5 shrink-0" />
            <span className="flex-1 text-left">Search…</span>
            <kbd className="bg-muted border-border hidden items-center gap-0.5 rounded border px-1 py-0.5 font-mono text-[10px] leading-none sm:inline-flex">
                ⌃K
            </kbd>
        </button>
    );
}
