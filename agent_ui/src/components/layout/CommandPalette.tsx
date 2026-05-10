import { useState } from "react";
import { useNavigate } from "react-router";
import {
    CommandDialog,
    Command,
    CommandInput,
    CommandList,
    CommandEmpty,
    CommandItem,
    CommandGroup,
} from "@/components/ui/command";
import { useMimirStore } from "@/store";

interface Props {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function CommandPalette({ open, onOpenChange }: Props) {
    const [query, setQuery] = useState("");
    const conversations = useMimirStore((s) => s.conversations);
    const navigate = useNavigate();

    const filtered = query
        ? conversations.filter((c) =>
              (c.title ?? c.id).toLowerCase().includes(query.toLowerCase())
          )
        : conversations.slice(0, 20);

    function select(id: string) {
        navigate(`/c/${id}`);
        onOpenChange(false);
        setQuery("");
    }

    return (
        <CommandDialog
            open={open}
            onOpenChange={(v) => {
                onOpenChange(v);
                if (!v) setQuery("");
            }}
            title="Search conversations"
            description="Type to search your conversations"
        >
            <Command shouldFilter={false}>
                <CommandInput
                    placeholder="Search conversations…"
                    value={query}
                    onValueChange={setQuery}
                />
                <CommandList>
                    <CommandEmpty>No conversations found.</CommandEmpty>
                    <CommandGroup heading={query ? "Results" : "Recent"}>
                        {filtered.map((c) => (
                            <CommandItem
                                key={c.id}
                                onSelect={() => select(c.id)}
                            >
                                {c.title ?? c.id}
                            </CommandItem>
                        ))}
                    </CommandGroup>
                </CommandList>
            </Command>
        </CommandDialog>
    );
}
